#!/usr/bin/env python3
"""Compare checked deep, shallow and hybrid effectful conditional embeddings."""

from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from io import BytesIO
from itertools import product
import json
import os
from pathlib import Path
import platform
import subprocess
from tarfile import open as open_tar
import tempfile

HERE = Path(__file__).resolve().parent
REVISION = "d83457c273e5b755f76add4b0d59cdeeed02e37e"
CALLS = "research/formal-verification/RT-32/GENERATED-CALL-01"
PROTOTYPE = "research/PROTOTYPES/DEPENDENCY-GRAPH-01"
INPUTS = (-3, -1, 0, 1, 2, 3, 5)


def literal(value):
    return json.dumps(value, ensure_ascii=False)


def prefix(pivot, offset, nested):
    argument = ["arg", "value"]
    condition = ["eq", ["emit", "left", argument], ["emit", "right", pivot]]
    yes = ["emit", "yes", ["add", argument, offset]]
    otherwise = ["sub", argument, offset]
    if nested:
        otherwise = ["if", ["eq", ["emit", "inner", argument], pivot + 1],
                     ["emit", "innerYes", ["sub", argument, offset + 1]],
                     ["emit", "innerNo", otherwise]]
    return ["if", condition, yes, ["emit", "no", otherwise]]


def infix(pivot, offset, nested):
    guard = f'(emit("left", x) == emit("right", {pivot}))'
    yes = f'emit("yes", x + {offset})'
    no = f'x - {offset}'
    if nested:
        no = (f'(emit("innerYes", x - {offset + 1}) if emit("inner", x) == {pivot + 1}'
              f' else emit("innerNo", {no}))')
    return f'({yes} if {guard} else emit("no", {no}))'


def expected(n, pivot, offset, nested):
    guard = ("left", "right")
    if n == pivot:
        return n + offset, (*guard, "yes")
    if not nested:
        return n - offset, (*guard, "no")
    label = "innerYes" if n == pivot + 1 else "innerNo"
    return n - offset - (n == pivot + 1), (*guard, "no", "inner", label)


def emit(term, style):
    constructors = {"argument": ".input", "literal": ".literal", "add": ".add",
                    "sub": ".sub", "emit": ".emit", "if": ".branch"}
    actions = {"argument": "input", "literal": "constant", "add": "binary Int.add",
               "sub": "binary Int.sub", "emit": "mark", "if": "choose"}
    tag, *operands = term
    operation = (constructors if style == "deep" else actions)[tag]
    match tag:
        case "argument":
            if operands != [0]:
                raise ValueError("outside admitted argument index")
            return operation
        case "literal":
            arguments = [f"({operands[0]})"]
        case "emit":
            arguments = [literal(operands[0]), emit(operands[1], style)]
        case "if":
            condition, yes, no = operands
            eq, left, right = condition
            if eq != "eq":
                raise ValueError("outside admitted condition")
            arguments = [emit(child, style) for child in (left, right, yes, no)]
        case _:
            arguments = [emit(child, style) for child in operands]
    return "(" + " ".join((operation, *arguments)) + ")"


def observations(calls):
    from src.spg_representation import Implementation, Operation, Prefix, Program

    rows = {}
    effects = (("left", "right", "yes"), ("left", "right", "no"),
               ("left", "right", "no", "inner", "innerYes"),
               ("left", "right", "no", "inner", "innerNo"))
    for number, (pivot, offset, nested) in enumerate(product((-1, 0, 2), (1, 3), (False, True))):
        graph = {}
        for notation, arg, body in (
            ("infix", "x", infix(pivot, offset, nested)),
            ("prefix", "value", Prefix(literal(prefix(pivot, offset, nested)))),
        ):
            program = Program({"ordered": effects},
                              {"run": Operation("Choose", ("Int",), "Int", "ordered")},
                              {"run": Implementation("run", (arg,), body)}, {})
            graph[notation] = calls.compile_program(program)
        source = graph["infix"]
        if source.snapshot != graph["prefix"].snapshot:
            raise AssertionError("Two source notations disagree at the SPG snapshot")
        address = source.snapshot.mapping["implementation:run"]
        raw = source.store.get(address).payload[2]["literal"]
        _, contract, _, term, references = calls.read_function(source, address)
        if references or json.loads(raw) != term:
            raise AssertionError("Unexpected stored SPG payload")
        result = []
        for n in INPUTS:
            wanted = expected(n, pivot, offset, nested)
            if any(calls.observe(current, "run", (n,)) != wanted for current in graph.values()):
                raise AssertionError((n, wanted, term))
            result.append((n, *wanted))
        rows[f"case{number:02}"] = {
            "snapshot": source.snapshot.root_hash, "body": address, "contract": contract,
            "wire": raw, "infix": infix(pivot, offset, nested),
            "prefix": prefix(pivot, offset, nested), "observations": result,
        }
    return rows


def lean_json(term):
    if isinstance(term, list):
        return "(Lean.Json.arr #[" + ", ".join(map(lean_json, term)) + "])"
    if type(term) is int:
        return f"(Lean.Json.num ⟨({term}), 0⟩)"
    if type(term) is bool:
        return "(Lean.Json.bool " + str(term).lower() + ")"
    return f"(Lean.Json.str {literal(term)})"


def positive_module(rows):
    lines = ["import Embedding", "open ScopedConditional", "set_option maxHeartbeats 4000000"]
    for name, row in rows.items():
        raw = row["wire"]
        term = json.loads(raw)
        lines.extend((
            f"def {name}Wire : String := {literal(raw)}",
            f"def {name}JSON : Lean.Json := {lean_json(term)}",
            f"#eval confirmParsed {name}Wire {name}JSON",
            f"def {name}Deep : Expr := {emit(term, 'deep')}",
            f"def {name}Shallow : Action := {emit(term, 'shallow')}",
            f"theorem {name}Decoded : decode 24 {name}JSON = some {name}Deep := by rfl",
            f"theorem {name}Generated : {name}Shallow = lower {name}Deep := by rfl",
            f"theorem {name}Correspondence (n : Int) :",
            f"    interpret {name}JSON n = some ({name}Shallow n) := by",
            f"  rw [{name}Generated]",
            f"  exact checked_wire_correspondence {name}JSON {name}Deep n {name}Decoded",
            f"#print axioms {name}Decoded",
            f"#print axioms {name}Correspondence",
        ))
        for n, value, trace in row["observations"]:
            lines.extend((f"example : {name}Shallow ({n}) = ⟨({value}), {literal(trace)}⟩ := by decide",
                          f"example : deep {name}Deep ({n}) = ⟨({value}), {literal(trace)}⟩ := by decide"))
    for raw in ('["argument",1]', '["literal",true]', '["op",0,["argument",0]]',
                '["if",["literal",7],["literal",0],["literal",0]]'):
        encoded = lean_json(json.loads(raw))
        lines.append(f"#eval confirmParsed {literal(raw)} {encoded}")
        lines.append(f"example : decode 24 {encoded} = none := by rfl")
    return "\n".join(lines) + "\n"


def lean_check(lean, directory, *options):
    return subprocess.run([lean, "-DwarningAsError=true", *options], cwd=directory,
                          env={**os.environ, "LEAN_PATH": str(directory)}, check=False,
                          text=True, capture_output=True)


def kernel(rows, directory):
    lean = os.environ.get("LEAN", "lean")
    core = directory / "Embedding.lean"
    core.write_bytes((HERE / core.name).read_bytes())
    proof = lean_check(lean, directory, "-o", "Embedding.olean", core.name)
    if proof.returncode or proof.stdout != (HERE / "axioms.txt").read_text():
        raise AssertionError((proof.stdout, proof.stderr))
    positive = positive_module(rows)
    (directory / "Positive.lean").write_text(positive)
    result = lean_check(lean, directory, "-o", "Positive.olean", "Positive.lean")
    if result.returncode or result.stderr or "sorryAx" in result.stdout:
        raise AssertionError((result.stdout, result.stderr))
    negatives = {
        "reversed_condition": '⟨(0), ["right", "left", "yes"]⟩',
        "eager_other_arm": '⟨(0), ["left", "right", "yes", "no"]⟩',
    }
    refusals = []
    for name, wrong in negatives.items():
        (directory / "Negative.lean").write_text(
            f"import Positive\nexample : case00Shallow (-1) = {wrong} := by rfl\n")
        checked = lean_check(lean, directory, "Negative.lean")
        if not checked.returncode or "rfl" not in checked.stdout:
            raise AssertionError((name, checked.stdout, checked.stderr))
        refusals.append(name)
    return {
        "generated_sha256": sha256(positive.encode()).hexdigest(),
        "axiom_audit": result.stdout.splitlines(),
        "version": subprocess.check_output([lean, "--version"], text=True).strip(),
        "parsed_byte_comparisons": len(rows) + 4,
        "closed_json_decodes": len(rows),
        "checked_ground_observations": len(rows) * len(INPUTS) * 2,
        "decoder_refusals": 4, "false_observations_refused": refusals,
    }


def main():
    with tempfile.TemporaryDirectory() as location:
        directory = Path(location)
        archive = subprocess.check_output(["git", "archive", REVISION, CALLS, PROTOTYPE])
        with open_tar(fileobj=BytesIO(archive), mode="r:") as exact:
            exact.extractall(directory, filter="data")
        loader = spec_from_file_location("conditional_spg", directory / CALLS / "run.py")
        calls = module_from_spec(loader)
        loader.loader.exec_module(calls)
        rows = observations(calls)
        checked = kernel(rows, directory)
    print(json.dumps({
        "schema": "llmlang-effectful-conditional-embeddings/1", "python": platform.python_version(),
        "archive_revision": REVISION,
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "Embedding.lean", "axioms.txt")},
        "cases": rows, "kernel": checked,
    }, indent=2))


if __name__ == "__main__":
    main()
