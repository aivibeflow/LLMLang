"""Map exact SPG terms into a typed Lean interpreter and check fuel correspondence."""
import argparse
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
dependency = spec_from_file_location("mutual_effects", HERE.parent / "MUTUAL-EFFECTS-01" / "run.py")
effects = module_from_spec(dependency)
dependency.loader.exec_module(effects)

from src.semantic_graph import canonical_bytes
from src.spg_representation import FuelExhausted, RepresentationError, observe


NONNEGATIVE = tuple(range(13))
NEGATIVE = (-1, -3, -17)
FUELS = tuple(range(17))
LEAN_PHASE = dict(zip(effects.MEMBERS, (".evenPhase", ".oddPhase"), strict=True))


def render_expr(term, references):
    match term:
        case ["literal", int(value)] if type(value) is int:
            return f"(.literal ({value}))"
        case ["argument", 0]:
            return ".argument"
        case [("add" | "sub" | "eq") as op, left, right]:
            return f"(.{op} {render_expr(left, references)} {render_expr(right, references)})"
        case ["if", test, yes, no]:
            return "(" + " ".join([".branch", *(render_expr(child, references) for child in (test, yes, no))]) + ")"
        case ["emit", str(event), body]:
            return f"(.emit {json.dumps(event)} {render_expr(body, references)})"
        case ["pin", int(index), operand] if type(index) is int and index in references:
            return f"(.call {references[index]} {render_expr(operand, references)})"
        case _:
            raise RepresentationError(f"unsupported term in typed recursive replay: {term!r}")


def generate(graph, subject, *, swap=False, off_by_one=False):
    group = graph.store.get(subject["group"]).payload
    positions = {data["position"]: LEAN_PHASE[member] for member, data in subject["members"].items()}
    typed = ["def checkedBody : Phase → Expr .integer"]
    for name in effects.MEMBERS:
        position = subject["members"][name]["position"]
        row = group[position]["body"]
        term = json.loads(row[2]["literal"])
        references = {index: positions[edge["local_call"]] for index, edge in enumerate(row[3:])}
        if swap and name == effects.MEMBERS[0]:
            tag, left, right = term[3]
            assert tag == "add"
            term[3] = [tag, right, left]
        typed.append(f"  | {LEAN_PHASE[name]} => {render_expr(term, references)}")
    shallow, footer = effects.generate(subject).split("\ndef main : IO Unit := do")
    assert footer
    deep = (HERE / "DeepFuel.lean.in").read_text(encoding="utf-8")
    deep = deep.replace("-- @TYPED_BODIES@", "\n".join(typed))
    if off_by_one:
        deep = deep.replace("if n < fuel then some (model phase n) else none",
                            "if n ≤ fuel then some (model phase n) else none")
    return f"{shallow}\n\n{deep}"


def evaluate(graph, name, n, fuel):
    try:
        value, trace = observe(graph, name, (n,), fuel=fuel)
    except FuelExhausted:
        return "exhausted"
    return f"{value}|{','.join(trace)}"


def check_profile(directory, policy):
    graph = effects.compile_program(effects.program(), policy)
    subject = effects.extract(graph)
    source = generate(graph, subject)
    output = directory / "DeepFuel.lean"
    output.write_text(source, encoding="utf-8")
    axioms = effects.quiet.run_lean(output)
    expected_audit = ("orderedPair", "generated_length", "deepShallow", "negativeExhausts")
    assert len(axioms) == len(expected_audit) and all(
        line.startswith(f"'{name}' depends on axioms:") and "sorryAx" not in line
        for line, name in zip(axioms, expected_audit, strict=True)
    )
    counts = {"in_budget": 0, "nonnegative_exhausted": 0, "negative_exhausted": 0}
    observations = []
    for n in NONNEGATIVE + NEGATIVE:
        for fuel in FUELS:
            for name in effects.MEMBERS:
                observed = evaluate(graph, name, n, fuel)
                if n >= 0 and fuel > n:
                    value, trace = effects.oracle(name, n)
                    assert observed == f"{value}|{','.join(trace)}", (policy, n, fuel, name)
                    counts["in_budget"] += 1
                else:
                    assert observed == "exhausted", (policy, n, fuel, name, observed)
                    key = "nonnegative_exhausted" if n >= 0 else "negative_exhausted"
                    counts[key] += 1
                observations.append(observed)
    actual = effects.quiet.run_lean(output, "--run")[-len(observations):]
    assert actual == observations
    return {"subject": subject, "counts": counts, "axioms": axioms,
            "lean_source_sha256": sha256(source.encode()).hexdigest(),
            "observation_sha256": sha256(canonical_bytes(observations)).hexdigest()}


def verify(directory):
    profiles = {name: check_profile(directory, name) for name in ("keyed", "structural")}
    graph = effects.compile_program(effects.program(), "keyed")
    subject = effects.extract(graph)
    rejected = directory / "Rejected.lean"
    controls = {}
    for label, options in (
        ("swapped_trace_operands", {"swap": True}),
        ("non_strict_fuel_test", {"off_by_one": True}),
    ):
        source = generate(graph, subject, **options)
        rejected.write_text(source, encoding="utf-8")
        effects.quiet.run_lean(rejected, expected="unsolved goals")
        controls[label] = {"diagnostic": "unsolved goals", "lean_source_sha256": sha256(source.encode()).hexdigest()}
    return {"format": "rt32-deep-fuel/1", "python": sys.version.split()[0],
            "lean": subprocess.check_output([*effects.quiet.LEAN, "--version"], text=True).strip(),
            "fuels": FUELS, "nonnegative": NONNEGATIVE, "negative": NEGATIVE,
            "profiles": profiles, "negative_controls": controls}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    opts = parser.parse_args()
    with TemporaryDirectory(prefix="rt32-deep-fuel-") as directory:
        result = verify(Path(directory))
    opts.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
