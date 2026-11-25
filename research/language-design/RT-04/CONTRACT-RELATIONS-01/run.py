"""Compare precise contract relations on a complete small outcome domain."""

import hashlib
import json
import platform
from itertools import product
from pathlib import Path

BASELINE = "4132c237b5f60e4326a5d1254a603085dd3cf4e3"
INPUTS = (-1, 0, 1)
SITE = (1,)  # Tuple index of the source value zero.
ALL = tuple(range(len(INPUTS)))
LEFT, RIGHT, ERROR = 1, 2, 4
OUTCOMES = {
    LEFT: {"result": ["Ok", 0], "effects": ["left", "right"]},
    RIGHT: {"result": ["Ok", 0], "effects": ["right", "left"]},
    ERROR: {"result": ["Range", None], "effects": ["failed"]},
}
OBSERVATIONS = tuple((index, outcome) for index in ALL for outcome in OUTCOMES)


def refines(public, provider, site=ALL):
    """Zero indicates explicit exclusion. An admitted outcome set is nonempty."""
    return all(not public[index] or (provider[index] and not provider[index] & ~public[index])
               for index in site)


def reference(public, provider, site):
    # Independent route over explicit input/outcome pairs and precondition failures.
    required_inputs = {index for index in site if public[index] != 0}
    provided_inputs = {index for index in site if provider[index] != 0}
    if not required_inputs <= provided_inputs:
        return False
    for index, outcome in OBSERVATIONS:
        if index in required_inputs and provider[index] & outcome and not public[index] & outcome:
            return False
    return True


def intersection_only(public, provider):
    shared = tuple(index for index in ALL if public[index] and provider[index])
    return refines(public, provider, shared)


def exhaustive():
    contracts = tuple(contract for contract in product(range(8), repeat=len(INPUTS)) if any(contract))
    counts = dict.fromkeys(("ordered_pairs", "equal_tables", "mutual_refinement", "global_refinement",
                            "callsite_refinement", "callsite_only_with_admitted_input",
                            "unsafe_intersection_only", "disjoint_unsafe_intersection_only"), 0)
    for public, provider in product(contracts, repeat=2):
        full = refines(public, provider)
        scoped = refines(public, provider, SITE)
        assert full == reference(public, provider, ALL), (public, provider)
        assert scoped == reference(public, provider, SITE), (public, provider)
        unsafe_intersection = intersection_only(public, provider) and not full
        counts["ordered_pairs"] += 1
        counts["equal_tables"] += public == provider
        counts["mutual_refinement"] += full and refines(provider, public)
        counts["global_refinement"] += full
        counts["callsite_refinement"] += scoped
        counts["callsite_only_with_admitted_input"] += scoped and not full and public[SITE[0]] != 0
        counts["unsafe_intersection_only"] += unsafe_intersection
        counts["disjoint_unsafe_intersection_only"] += unsafe_intersection and not any(
            public[index] and provider[index] for index in ALL
        )
    return len(contracts), counts


def address(table, profile):
    wire = json.dumps({"fixture_profile": profile, "allowed_outcome_masks": table},
                      sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(wire).hexdigest()


def body_status(contract, actual):
    insufficient = False
    for index in ALL:
        if not contract[index]:
            continue
        outcomes = actual[index]
        if outcomes is None:
            insufficient = True
        elif not outcomes or outcomes & ~contract[index]:
            return "REFUTED"
    return "UNKNOWN" if insufficient else "CHECKED"


def project(mask, *, full):
    return {json.dumps(event if full else event["result"], sort_keys=True)
            for bit, event in OUTCOMES.items() if mask & bit}


def controls():
    public = (0, LEFT | RIGHT, LEFT)
    stronger = (ERROR, LEFT, LEFT)
    restricted = (0, LEFT, 0)
    disjoint = (ERROR, 0, 0)
    old_body = (None, LEFT, LEFT)
    new_body = (None, RIGHT, LEFT)
    missing = (None, None, LEFT)
    wrong = (None, ERROR, LEFT)

    results = {
        "equal_denotation_distinct_exact_bytes": {
            "first_sha256": address(public, "profile-a"),
            "second_sha256": address(public, "profile-b"),
            "mutual_refinement": refines(public, public),
        },
        "wider_precondition_narrower_outcomes": refines(public, stronger),
        "restricted_provider_global": refines(public, restricted),
        "restricted_provider_at_zero": refines(public, restricted, SITE),
        "disjoint_comparison_wrongly_accepted": intersection_only(public, disjoint),
        "disjoint_global": refines(public, disjoint),
        "old_body_conformance": body_status(public, old_body),
        "new_body_conformance": body_status(public, new_body),
        "missing_body_conformance": body_status(public, missing),
        "wrong_body_conformance": body_status(public, wrong),
        "result_equivalence_at_zero": project(old_body[1], full=False) == project(new_body[1], full=False),
        "full_observation_equivalence_at_zero": project(old_body[1], full=True) == project(new_body[1], full=True),
        "old_at_zero": OUTCOMES[old_body[1]],
        "new_at_zero": OUTCOMES[new_body[1]],
    }
    assert results["wider_precondition_narrower_outcomes"]
    assert results["restricted_provider_at_zero"] and not results["restricted_provider_global"]
    assert results["disjoint_comparison_wrongly_accepted"] and not results["disjoint_global"]
    assert results["old_body_conformance"] == results["new_body_conformance"] == "CHECKED"
    assert results["missing_body_conformance"] == "UNKNOWN" and results["wrong_body_conformance"] == "REFUTED"
    assert results["result_equivalence_at_zero"] and not results["full_observation_equivalence_at_zero"]
    assert results["equal_denotation_distinct_exact_bytes"]["first_sha256"] != results[
        "equal_denotation_distinct_exact_bytes"]["second_sha256"]
    return results


def main():
    contracts, counts = exhaustive()
    print(json.dumps({
        "baseline": BASELINE, "python": platform.python_version(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "input_domain": INPUTS, "callsite_input": INPUTS[SITE[0]], "outcomes": OUTCOMES,
        "contracts": contracts, "counts": counts, "controls": controls(),
    }, indent=2))


if __name__ == "__main__":
    main()
