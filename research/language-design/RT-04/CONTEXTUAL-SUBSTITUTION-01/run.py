#!/usr/bin/env python3
"""Compare contract judgments with deterministic adaptive client observations."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
JOINT = HERE.parent / "JOINT-CONTRACTS-01"
sys.path.insert(0, str(JOINT))
from run import Contract, candidates, execute, native

PROFILES = {
    "complete": (lambda observation: observation[0] + 2 * observation[1], 4),
    "result_only": (lambda observation: observation[0], 2),
    "event_only": (lambda observation: observation[1], 2),
}


def fingerprint(value):
    return sha256(json.dumps(value, separators=(",", ":")).encode("ascii")).hexdigest()


def run_client(observed, first, branches):
    first_value = observed[first]
    if branches is None:
        return (first_value,)
    return first_value, observed[branches[first_value]]


def refines(provided, required):
    if required.eligible & provided.eligible != required.eligible:
        return False
    return all(not required.active(i) or not (provided.raw(i) & ~required.raw(i)) for i in (0, 1))


def contract_controls(families):
    table = candidates(families)
    same_a, same_b = Contract(1, 5, 1), Contract(1, 5, 2)
    result_only, quiet = Contract(3, 5, 10), Contract(3, 1, 2)
    same_exact = fingerprint(same_a.fields()) == fingerprint(same_b.fields())
    same_effective = all(same_a.effective(index) == same_b.effective(index) for index in (0, 1))
    if same_exact or not same_effective:
        raise AssertionError("Inactive fields must distinguish the artifact control")
    if not refines(quiet, result_only) or refines(result_only, quiet):
        raise AssertionError("The strict contract must refine in just one direction")
    holder_mask = table[(result_only.effective(0), result_only.effective(1))]
    if not all(holder_mask & (1 << provider) for provider in (4, 14)):
        raise AssertionError("Both providers must satisfy the same result-only declaration")
    old, new = families[4], families[14]
    route = (0, 0, 1, 0)
    projected_old = [PROFILES["complete"][0](old[index]) for index in (0, 1)]
    projected_new = [PROFILES["complete"][0](new[index]) for index in (0, 1)]
    left = run_client(projected_old, 0, route)
    right = run_client(projected_new, 0, route)
    if (left[-1] & 1, right[-1] & 1) != (0, 1):
        raise AssertionError("The callback observation should influence the adaptive caller result")
    return {
        "different_declarations_same_effective_contract": {
            "left": same_a.fields(), "right": same_b.fields(), "exact_equal": same_exact,
            "effective_equal": same_effective,
        },
        "strict_to_permissive_refines": refines(quiet, result_only),
        "permissive_to_strict_refines": refines(result_only, quiet),
        "same_contract_different_adaptive_result": {
            "contract": result_only.fields(), "left_provider": 4, "right_provider": 14,
            "routing_input_by_first_observation": route, "left_observations": left,
            "right_observations": right, "final_boolean_results": [left[-1] & 1, right[-1] & 1],
        },
    }


def run():
    families, native_sha = native()
    counts = {profile: Counter() for profile in PROFILES}
    traces = {}
    for profile, (project, alphabet) in PROFILES.items():
        observed = {identity: [project(function[index]) for index in (0, 1)]
                    for identity, function in families.items()}
        for inputs in ((0,), (1,), (0, 1)):
            clients = [(first, None) for first in inputs]
            clients += [(first, branches) for first in inputs for branches in product(inputs, repeat=alphabet)]
            generated = {identity: [run_client(seen, first, branches) for first, branches in clients]
                         for identity, seen in observed.items()}
            for left, right in product(observed, repeat=2):
                pointwise = all(observed[left][index] == observed[right][index] for index in inputs)
                identical = generated[left] == generated[right]
                if pointwise != identical:
                    raise AssertionError((profile, inputs, left, right))
                counts[profile]["provider_domain_pairs"] += 1
                counts[profile]["context_comparisons"] += len(clients)
                counts[profile]["contextually_indistinguishable"] += identical
            traces[f"{profile}:{inputs}"] = fingerprint(generated)
    return {
        "schema": "llmlang-contextual-substitution/1", "python": platform.python_version(),
        "gcc": execute(["gcc", "--version"], HERE).splitlines()[0],
        "sources_sha256": {
            **{name: sha256((HERE / name).read_bytes()).hexdigest()
               for name in ("Context.lean", "axioms.txt", "run.py")},
            "native_reference_runner": sha256((JOINT / "run.py").read_bytes()).hexdigest(),
            "native_probe": sha256((JOINT / "probe.c").read_bytes()).hexdigest(),
        },
        "native_rows_sha256": native_sha, "comparison_counts": counts,
        "scoped_observations_sha256": traces, "controls": contract_controls(families),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
