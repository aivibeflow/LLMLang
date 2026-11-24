#!/usr/bin/env python3
"""Observe exact SPG fixture calls and compare finite contract judgments."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from run import METHODS, encode_lean, python_decisions

HERE = Path(__file__).resolve().parent
SPG = HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(SPG))

from src.spg_representation import (  # noqa: E402
    FuelExhausted, Implementation, Operation, Prefix, Program, RepresentationError,
    compile_program, observe,
)

INPUTS = (0, 1, 2)
BODIES = {
    "primary": ('emit("first", emit("last", n + 1))',
                ["emit", "first", ["emit", "last", ["add", ["arg", "n"], 1]]]),
    "alternate": ('emit("first", emit("last", n + 2))',
                  ["emit", "first", ["emit", "last", ["add", ["arg", "n"], 2]]]),
    "reordered": ('emit("last", emit("first", n + 1))',
                  ["emit", "last", ["emit", "first", ["add", ["arg", "n"], 1]]]),
    "omitted": ('emit("first", n + 1)', ["emit", "first", ["add", ["arg", "n"], 1]]),
}

# Expected verdict order is signature, direct public body, separate body/refinement.
CASES = (
    ("base-operation", "primary", "op", "both", 64, ("admit", "admit", "admit")),
    ("rebound-operation", "alternate", "op", "both", 64, ("admit", "admit", "admit")),
    ("rebound-operation-stale-provider-contract", "alternate", "op", "primary", 64, ("admit", "admit", "reject")),
    ("rebound-direct", "alternate", "pin", "primary", 64, ("admit", "admit", "admit")),
    ("reordered-operation", "reordered", "op", "both", 64, ("admit", "reject", "reject")),
    ("omitted-effect-operation", "omitted", "op", "both", 64, ("admit", "reject", "reject")),
    ("exhausted-operation", "primary", "op", "both", 1, ("admit", "unknown", "unknown")),
)


def term(text, prefix, surface):
    return text if surface == "infix" else Prefix(json.dumps(prefix))


def graph_for(provider, call_mode, surface, *, bad_result=False):
    contract = {"trace": (("first", "last"),)}
    operations = {name: Operation(export, ("Int",), "Int", "trace")
                  for name, export in (("provide", "Provide"), ("entry", "Entry"))}
    implementations = {
        name: Implementation("provide", ("n",), term(text, prefix, surface))
        for name, (text, prefix) in BODIES.items()
    }
    if bad_result:
        implementations["primary"] = Implementation("provide", ("n",), "True")
    target = "provide" if call_mode == "op" else "primary"
    implementations["entry"] = Implementation(
        "entry", ("n",), term(f'{call_mode}("{target}", n)', [call_mode, target, ["arg", "n"]], surface)
    )
    return compile_program(Program(contract, operations, implementations, {"provide": provider}))


def expected_observation(provider, call_mode, value, fuel):
    if fuel == 1:
        return None
    actual = provider if call_mode == "op" else "primary"
    return value + (2 if actual == "alternate" else 1), {
        "primary": ("first", "last"), "alternate": ("first", "last"),
        "reordered": ("last", "first"), "omitted": ("first",),
    }[actual]


def observe_all(graph, fuel):
    values = {}
    for value in INPUTS:
        try:
            values[value] = observe(graph, "entry", (value,), fuel=fuel)
        except FuelExhausted:
            values[value] = None
    return values


def build_fixture():
    data = {"observations": {}, "contracts": {"both": {}, "primary": {}}, "bodies": {}, "cases": []}
    tags = {}

    def add_observation(result):
        if result is None:
            return None
        if result not in tags:
            label = f"outcome-{len(tags)}"
            value, trace = result
            data["observations"][label] = {
                "status": "ok", "value": value, "trace": list(trace), "ownership": "unmodeled-scalar",
            }
            tags[result] = label
        return tags[result]

    for value in INPUTS:
        left, right = [add_observation((value + offset, ("first", "last"))) for offset in (1, 2)]
        data["contracts"]["both"][str(value)] = [left, right]
        data["contracts"]["primary"][str(value)] = [left]

    evidence = []
    for name, provider, mode, provided, fuel, expected in CASES:
        infix, prefix = [graph_for(provider, mode, surface) for surface in ("infix", "prefix")]
        observed = observe_all(infix, fuel)
        oracle = {value: expected_observation(provider, mode, value, fuel) for value in INPUTS}
        if observed != oracle or observe_all(prefix, fuel) != oracle:
            raise ValueError(f"Source observation mismatch in {name}")
        if infix.snapshot.root_hash != prefix.snapshot.root_hash:
            raise ValueError(f"Surface-dependent snapshot identity in {name}")
        data["bodies"][name] = {str(inp): add_observation(value) for inp, value in observed.items()}
        case = {"name": name, "public": "both", "provided": provided, "body": name,
                "signature": True, "expected": list(expected)}
        actual = python_decisions(case, data)
        if tuple(actual) != expected:
            raise ValueError(f"Contract decision mismatch in {name}")
        data["cases"].append(case)
        selected = infix.snapshot.mapping
        called = provider if mode == "op" else "primary"
        evidence.append({
            "case": name, "call_mode": mode, "operation_binding_provider": provider,
            "called_provider": called, "called_implementation": selected[f"implementation:{called}"],
            "provided_contract": provided, "fuel": fuel, "source_surfaces_matched": True,
            "snapshot": infix.snapshot.root_hash, "entry": selected["implementation:entry"],
            "binding": selected["binding:provide"], "observations": observed,
            "verdicts": dict(zip(METHODS, actual, strict=True)),
        })

    base, rebound = evidence[:2]
    if base["entry"] != rebound["entry"] or base["binding"] == rebound["binding"]:
        raise ValueError("Expected a stable call body under an exact provider rebind")
    return data, evidence


def run(lean):
    try:
        graph_for("primary", "op", "infix", bad_result=True)
    except RepresentationError:
        ill_typed_rejected = True
    else:
        raise ValueError("Bool body admitted under an Int result signature")

    data, evidence = build_fixture()
    generated = encode_lean(data)
    with TemporaryDirectory(prefix="llmlang-spg-refinement-") as scratch:
        theorem = Path(scratch) / "Check.lean"
        theorem.write_text(generated, encoding="utf-8")
        checked = subprocess.run([lean, "-DwarningAsError=true", str(theorem)], check=True,
                                 capture_output=True, text=True, timeout=30)
        if checked.stderr or checked.stdout.strip() != "'checkedCases' does not depend on any axioms":
            raise ValueError(f"Unexpected Lean theorem audit: {checked.stdout + checked.stderr}")

    return {
        "schema": "llmlang-spg-observed-provider-refinement-v1",
        "python": sys.version,
        "lean": subprocess.check_output([lean, "--version"], text=True).strip(),
        "input_sha256": {
            file.name: sha256(file.read_bytes()).hexdigest()
            for file in (Path(__file__), HERE / "run.py", HERE / "Refinement.lean",
                         SPG / "src/spg_representation.py", SPG / "src/semantic_graph.py")
        },
        "generated_lean_sha256": sha256(generated.encode()).hexdigest(),
        "lean_axioms": checked.stdout.strip(),
        "ill_typed_body_rejected": ill_typed_rejected,
        "cases": evidence,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", default="lean")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.lean)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for case in result["cases"]:
        print(case["case"], case["verdicts"])
