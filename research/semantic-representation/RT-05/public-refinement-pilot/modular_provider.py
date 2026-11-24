#!/usr/bin/env python3
"""Compare observed typed-SPG provider calls with a modular Lean caller theorem."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from spg_observations import BODIES, SPG, term

from src.spg_representation import (  # noqa: E402
    FuelExhausted, Implementation, Operation, Program, compile_program, observe,
)

HERE = Path(__file__).resolve().parent
INPUTS = (-5, 0, 1, 2, 17)
CALLER = (
    'emit("before", op("provide", n) + emit("after", 10))',
    ["emit", "before", ["add", ["op", "provide", ["arg", "n"]], ["emit", "after", 10]]],
)
PROVIDERS = {
    **BODIES,
    "outOfRange": (
        'emit("first", emit("last", n + 3))',
        ["emit", "first", ["emit", "last", ["add", ["arg", "n"], 3]]],
    ),
}
CASES = (
    ("primary", "primary", 64),
    ("alternate", "alternate", 64),
    ("reordered", "reordered", 64),
    ("outOfRange", "outOfRange", 64),
    ("missing", "primary", 1),
)
AUDITED_THEOREMS = (
    "reusableCaller", "primaryCaller", "reboundCaller",
    "rejectsReordered", "rejectsOutOfRange", "rejectsMissing",
)


def graph_for(provider, surface):
    contracts = {"ordered": (("first", "last"),), "framed": (("before", "first", "last", "after"),)}
    operations = {
        "provide": Operation("Provide", ("Int",), "Int", "ordered"),
        "entry": Operation("Entry", ("Int",), "Int", "framed"),
    }
    implementations = {
        name: Implementation("provide", ("n",), term(text, prefix, surface))
        for name, (text, prefix) in PROVIDERS.items()
    }
    implementations["entry"] = Implementation("entry", ("n",), term(*CALLER, surface))
    return compile_program(Program(contracts, operations, implementations, {"provide": provider}))


def observe_or_missing(graph, entry, value, fuel):
    try:
        return observe(graph, entry, (value,), fuel=fuel)
    except FuelExhausted:
        return None


def lean_int(value):
    return f"({value} : Int)"


def lean_option(observed):
    if observed is None:
        return "none"
    value, trace = observed
    return f"some ({lean_int(value)}, {json.dumps(trace)})"


def run(lean):
    proof = HERE / "ModularCaller.lean"
    fixture = [proof.read_text(encoding="utf-8"), "open ModularCaller"]
    evidence = {}
    for model, provider, fuel in CASES:
        graphs = [graph_for(provider, surface) for surface in ("infix", "prefix")]
        snapshot = graphs[0].snapshot
        if snapshot != graphs[1].snapshot:
            raise ValueError(f"{model}: semantically equivalent surfaces compiled differently")

        rows = []
        for value in INPUTS:
            pairs = [
                (observe_or_missing(graph, provider, value, fuel - 1),
                 observe_or_missing(graph, "entry", value, fuel))
                for graph in graphs
            ]
            if pairs[0] != pairs[1]:
                raise ValueError(f"{model}: observation differed across surfaces at {value}")
            member_result, caller_result = pairs[0]
            fixture.extend((
                f"example : {model} {lean_int(value)} = {lean_option(member_result)} := by decide",
                f"example : caller {model} {lean_int(value)} = {lean_option(caller_result)} := by decide",
            ))
            rows.append({"input": value, "provider": member_result, "caller": caller_result})

        evidence[model] = {
            "selected_provider": provider,
            "binding": snapshot.mapping["binding:provide"],
            "caller": snapshot.mapping["implementation:entry"],
            "caller_budget": fuel,
            "observations": rows,
        }
    primary, alternate = (evidence[name] for name in ("primary", "alternate"))
    if primary["caller"] != alternate["caller"] or primary["binding"] == alternate["binding"]:
        raise ValueError("Compatible replacement must preserve caller identity and change binding")

    source = "\n".join(fixture) + "\n"
    with TemporaryDirectory(prefix="llmlang-modular-provider-") as scratch:
        generated = Path(scratch) / "Check.lean"
        generated.write_text(source, encoding="utf-8")
        checked = subprocess.run([lean, "-DwarningAsError=true", str(generated)], check=True,
                                 capture_output=True, text=True, timeout=30)
    expected = [f"'ModularCaller.{name}' does not depend on any axioms" for name in AUDITED_THEOREMS]
    if checked.stderr or checked.stdout.splitlines() != expected:
        raise ValueError(f"Unexpected Lean theorem audit: {checked.stdout + checked.stderr}")

    return {
        "schema": "llmlang-modular-typed-spg-provider-v1",
        "python": sys.version,
        "lean": subprocess.check_output([lean, "--version"], text=True).strip(),
        "input_sha256": {
            file.name: sha256(file.read_bytes()).hexdigest()
            for file in (proof, Path(__file__), HERE / "spg_observations.py", SPG / "src/spg_representation.py")
        },
        "generated_lean_sha256": sha256(source.encode()).hexdigest(),
        "axiom_free_theorems": list(AUDITED_THEOREMS),
        "finite_observations": len(CASES) * len(INPUTS) * 2 * 2,
        "kernel_checked_observation_equalities": len(CASES) * len(INPUTS) * 2,
        "cases": evidence,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", default="lean")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    data = run(args.lean)
    args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"{data['finite_observations']} observations, {data['kernel_checked_observation_equalities']} Lean equalities")
