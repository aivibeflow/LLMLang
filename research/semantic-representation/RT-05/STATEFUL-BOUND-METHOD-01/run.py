#!/usr/bin/env python3
"""Compare capture and state-topology projections against native C and Rust methods."""

from hashlib import sha256
from itertools import chain, combinations, product
import json
import os
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
DOMAIN = "llmlang-rt05-stateful-bound-method/1"
POLICIES = ("code_only", "values_only", "exact")
INITIAL_VALUES = (-3, 0, 4)
BIASES = (-2, 0, 3)
METHOD = ["Rule", "step", "bounded-signed-int-update/1"]
RECIPES = (
    ((0, 0, 0), (0, 1, 0), (1, 0, 2), (0, 1, 0), (1, 1, -1), (0, 0, 0)),
    ((0, 1, 0), (1, 1, 1), (1, 0, 1), (2, 0, 6), (0, 1, 0)),
    ((2, 1, -5), (0, 0, 0), (1, 0, -2), (0, 1, 0), (1, 1, 2)),
    ((1, 0, 10), (1, 1, 10), (1, 0, 0), (1, 1, -3), (0, 0, 0), (0, 1, 0)),
    ((0, 1, 0), (2, 0, 3), (0, 1, 0), (2, 1, -1), (0, 0, 0)),
)


def digest(data):
    return sha256(data).hexdigest()


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def identity(data):
    return digest(DOMAIN.encode() + b"\0" + canonical(data).encode())


def contexts():
    separate = [(False, *values) for values in product(INITIAL_VALUES, INITIAL_VALUES, BIASES, BIASES)]
    shared = [(True, value, value, left, right) for value, left, right in product(INITIAL_VALUES, BIASES, BIASES)]
    return [*separate, *shared]


def descriptor(policy, context):
    aliases, first, second, left, right = context
    if policy == "code_only":
        return {"code": METHOD}
    if policy == "values_only":
        return {"code": METHOD, "receivers": [[first, left], [second, right]]}
    assert policy == "exact"
    cells = [first] if aliases else [first, second]
    receivers = [[0, left], [0 if aliases else 1, right]]
    return {"code": METHOD, "receivers": receivers, "cells": cells}


def restore(graph, policy):
    if graph["code"] != METHOD:
        raise ValueError("method")
    if policy == "code_only":
        return False, 0, 0, 0, 0
    (left_location, left_bias), (right_location, right_bias) = graph["receivers"]
    if policy == "values_only":
        return False, left_location, right_location, left_bias, right_bias
    cells = graph["cells"]
    if not all(type(address) is int and 0 <= address < len(cells) for address in (left_location, right_location)):
        raise ValueError("missing-cell")
    if {left_location, right_location} != set(range(len(cells))):
        raise ValueError("unused-cell")
    return left_location == right_location, cells[left_location], cells[right_location], left_bias, right_bias


def projection(policy, context):
    return restore(json.loads(canonical(descriptor(policy, context))), policy)


def controls():
    baseline = descriptor("exact", (True, 0, 0, 0, 0))
    results = {}
    for expected, change in (("method", {"code": ["Other"]}), ("missing-cell", {"receivers": [[0, 0], [1, 0]]}),
                             ("unused-cell", {"cells": [0, 5]})):
        try:
            restore({**baseline, **change}, "exact")
        except ValueError as error:
            results[expected] = str(error)
        assert results.get(expected) == expected
    return results


def reference(context, recipe):
    aliases, first, second, left, right = context
    state = [first, second]
    bias = [left, right]
    trace = []
    for kind, slot, argument in recipe:
        cell = 0 if aliases else slot
        before = state[cell]
        state[cell] = (before, before + bias[slot] + argument, argument)[kind]
        trace.extend((before, state[cell]))
    return trace


def normalize_row(context, recipe):
    return " ".join(map(str, (int(context[0]), *context[1:], len(recipe), *chain.from_iterable(recipe))))


def command(directory, *argv, data=None):
    result = subprocess.run(argv, cwd=directory, input=data, check=True, text=True, capture_output=True,
                            timeout=45, env={**os.environ, "LC_ALL": "C"})
    return result.stdout


def native(directory, rows):
    profiles = {
        "c_O0": ["gcc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-O0", str(HERE / "observe.c")],
        "c_O2": ["gcc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2", str(HERE / "observe.c")],
        "rust_O0": ["rustc", "--edition", "2021", "-D", "warnings", "-C", "opt-level=0", str(HERE / "observe.rs")],
        "rust_O3": ["rustc", "--edition", "2021", "-D", "warnings", "-C", "opt-level=3", str(HERE / "observe.rs")],
    }
    payload = "\n".join(normalize_row(context, recipe) for context, recipe in rows) + "\n"
    result = {}
    for name, argv in profiles.items():
        binary = directory / name
        command(directory, *argv, "-o", str(binary))
        observed = [list(map(int, line.split())) for line in command(directory, str(binary), data=payload).splitlines()]
        assert len(observed) == len(rows)
        assert all(values[:2] == [1, int(context[0])] and values[2:] == reference(context, recipe)
                   for values, (context, recipe) in zip(observed, rows, strict=True)), name
        result[name] = observed
    return result


def run(directory):
    assert platform.system() == "Linux" and platform.machine() == "x86_64"
    corpus = contexts()
    modes = ("raw", *POLICIES)
    rows = [(context if mode == "raw" else projection(mode, context), recipe)
            for context, mode, recipe in product(corpus, modes, RECIPES)]
    profiles = native(directory, rows)
    witness_count = sum(row[0] for data in profiles.values() for row in data)
    baseline = iter(profiles["c_O0"])
    metrics = {policy: dict(changed_recipe_vectors=0, colliding_context_pairs=0,
                           colliding_pairs_with_different_traces=0) for policy in POLICIES}
    observations = []
    for context in corpus:
        trace_sets = {mode: [next(baseline)[2:] for _ in RECIPES] for mode in modes}
        choices = {}
        for policy in POLICIES:
            drift = [[recipe, actual] for recipe, (expected, actual) in enumerate(zip(trace_sets["raw"], trace_sets[policy], strict=True))
                     if expected != actual]
            metrics[policy]["changed_recipe_vectors"] += len(drift)
            choices[policy] = {"key": identity(descriptor(policy, context)), "differences": drift}
        observations.append({"context": context, "reference": trace_sets["raw"], "choices": choices})
    assert next(baseline, None) is None
    for left, right in combinations(observations, 2):
        for policy in POLICIES:
            if left["choices"][policy]["key"] == right["choices"][policy]["key"]:
                metrics[policy]["colliding_context_pairs"] += 1
                metrics[policy]["colliding_pairs_with_different_traces"] += left["reference"] != right["reference"]
    assert not any(metrics["exact"].values())
    assert metrics["values_only"]["colliding_pairs_with_different_traces"] == 27
    assert metrics["code_only"]["colliding_pairs_with_different_traces"] > 4000
    total = len(rows) * len(profiles)
    assert witness_count == total
    return {"schema": DOMAIN, "python": platform.python_version(),
            "gcc": command(directory, "gcc", "--version").splitlines()[0],
            "rustc": command(directory, "rustc", "-vV").splitlines(),
            "sources": {name: digest((HERE / name).read_bytes()) for name in ("run.py", "observe.c", "observe.rs")},
            "profiles": list(profiles), "recipes": RECIPES, "contexts": len(corpus),
            "total_native_recipe_vectors": total, "equal_code_or_type_witnesses": witness_count,
            "metrics": metrics, "controls": controls(), "observations": observations}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt05-stateful-method-") as scratch:
        outcome = run(Path(scratch))
    rows = outcome.pop("observations")
    print(json.dumps(outcome, indent=2).removesuffix("\n}") + ',\n  "observations": [')
    print(",\n".join("    " + canonical(row) for row in rows))
    print("  ]\n}")
