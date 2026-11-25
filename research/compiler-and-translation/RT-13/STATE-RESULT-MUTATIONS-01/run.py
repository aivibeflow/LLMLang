#!/usr/bin/env python3
"""Compare observation projections and value generators on bounded rewrite controls."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import random
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REFERENCE = ROOT / "research/formal-verification/RT-07/STATE-RESULT-REFERENCE-01"
sys.path.insert(0, str(REFERENCE))
import reference

LEAVES = (("skip",), ("read",), ("fail",), ("write", 0), ("write", 1))
FORMERS = ("bind", "strict", "then", "else")
MUTATIONS = ("ignore_left_failure", "short_circuit_strict", "drop_overwritten_write",
             "exchange_write_order", "drop_read", "run_skipped_branch")
SEED = 17707


def optimize(program):
    tag = program[0]
    if tag in ("then", "else"):
        return optimize(program[1 if tag == "then" else 2])
    if tag in ("bind", "strict"):
        left, right = (optimize(child) for child in program[1:])
        if left == ("skip",):
            return right
        return tag, left, right
    return program


def mutate(program, mutant):
    tag = program[0]
    if tag not in FORMERS:
        if tag == "read" and mutant == "drop_read":
            return ("skip",)
        return program
    left, right = (mutate(child, mutant) for child in program[1:])
    if tag == "bind" and mutant == "ignore_left_failure":
        return "strict", left, right
    if tag == "strict" and mutant == "short_circuit_strict":
        return "bind", left, right
    if tag in ("then", "else") and mutant == "run_skipped_branch":
        return "strict", left, right
    if tag == "strict" and left[0] == right[0] == "write":
        if mutant == "drop_overwritten_write":
            return right
        if mutant == "exchange_write_order":
            return "strict", right, left
    return tag, left, right


def observe(program, initial):
    request = json.dumps([reference.SCHEMA, initial, program], separators=(",", ":")).encode("ascii")
    result = reference.evaluate_request(request)
    return (next(iter(result["result"].items())), result["final_cell"],
            tuple(tuple(event) for event in result["trace"]))


def machine(program, initial):
    model = reference.model
    expression = model.ast_for(program)
    raw = model.observed(model.run_small_step(
        expression, "D", declared_effects=model.EFFECTS, initial_state={"cell": initial},
    ))
    return raw[0], raw[1], tuple(tuple(event) for event in raw[2])


def project(observation):
    result, cell, trace = observation
    return {
        "result": result, "cell": cell, "result_and_cell": (result, cell),
        "event_multiset": (result, cell, tuple(sorted(trace))),
        "complete": observation,
    }


def generated(leaves, formers, samples, maximum_depth, seed):
    rng = random.Random(seed)

    def draw(depth):
        if not depth or rng.randrange(4) == 0:
            return rng.choice(leaves)
        return rng.choice(formers), draw(depth - 1), draw(depth - 1)

    return [draw(rng.randrange(maximum_depth + 1)) for _ in range(samples)]


def size(program):
    return 1 + sum(size(child) for child in program[1:] if isinstance(child, tuple))


def evaluate_corpus(programs):
    distinct = sorted(set(programs), key=lambda program: (size(program), program))
    counts = {mutant: Counter() for mutant in MUTATIONS}
    witnesses = {}
    projection_witnesses = {}
    digest = sha256()
    for program, cell in product(distinct, (0, 1)):
        expected = observe(program, cell)
        safe = optimize(program)
        if observe(safe, cell) != expected or machine(program, cell) != expected or machine(safe, cell) != expected:
            raise AssertionError(f"Candidate or independent machine differs on {program}, {cell}")
        left = project(expected)
        for mutant in MUTATIONS:
            emitted = optimize(mutate(program, mutant))
            actual = observe(emitted, cell)
            right = project(actual)
            differences = [name for name in left if left[name] != right[name]]
            counts[mutant].update(differences)
            if differences:
                missed = "event_multiset" not in differences
                if mutant not in witnesses or (missed and mutant not in projection_witnesses):
                    if actual != machine(emitted, cell):
                        raise AssertionError(f"Independent machine disagrees on {mutant}, {program}, {cell}")
                    witness = {
                        "program": program, "initial": cell, "emitted": emitted,
                        "expected": expected, "actual": actual, "different_projections": differences,
                    }
                    witnesses.setdefault(mutant, witness)
                    if missed:
                        projection_witnesses.setdefault(mutant, witness)
            row = (program, cell, mutant, emitted, expected, actual)
            digest.update(json.dumps(row, separators=(",", ":")).encode("ascii") + b"\n")

    zeros = dict.fromkeys(project((None, 0, ())), 0)
    return {
        "generated_programs": len(programs), "distinct_programs": len(distinct),
        "source_initial_profiles": 2 * len(distinct),
        "checked_mutant_observations": 2 * len(distinct) * len(MUTATIONS),
        "differences": {mutant: zeros | count for mutant, count in counts.items()},
        "first_complete_witnesses": witnesses,
        "first_order_only_witnesses": projection_witnesses,
        "comparison_rows_sha256": digest.hexdigest(),
    }


def run():
    exhaustive = list(reference.model.corpus())
    corpora = {
        "bounded_exhaustive": evaluate_corpus(exhaustive),
        "seeded_general": evaluate_corpus(generated(LEAVES, FORMERS, 2048, 7, SEED)),
        "seeded_success_only": evaluate_corpus(generated(
            tuple(leaf for leaf in LEAVES if leaf[0] != "fail"), FORMERS, 2048, 7, SEED,
        )),
    }
    if not all(row["complete"] for row in corpora["bounded_exhaustive"]["differences"].values()):
        raise AssertionError("A configured mutation has no distinguishing control")
    if any(corpora["seeded_success_only"]["differences"][name]["complete"]
           for name in ("ignore_left_failure", "short_circuit_strict")):
        raise AssertionError("A short-circuit control unexpectedly differs on an error-free program")
    files = [
        Path(__file__), REFERENCE / "reference.py", reference.MODEL,
        reference.model.PROTOTYPE / "rt03_reference.py", reference.model.PROTOTYPE / "rt03_smallstep.py",
    ]
    return {
        "schema": "llmlang-state-result-test-coverage/1", "python": platform.python_version(), "seed": SEED,
        "sources_sha256": {file.relative_to(ROOT).as_posix(): sha256(file.read_bytes()).hexdigest()
                           for file in files},
        "corpora": corpora,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
