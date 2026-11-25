"""Compare a bounded reconstruction workflow across requirement classes."""

import hashlib
import importlib.util
from itertools import product
import json
from pathlib import Path
import platform

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ROUNDTRIP = HERE.parent / "RECONSTRUCTION-ROUNDTRIP-01"
SPEC = importlib.util.spec_from_file_location("temporal_fixture", ROUNDTRIP / "run.py")
TEMPORAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TEMPORAL)

POLICIES = {
    "routine": ("FINITE_ENUMERATION", "FINITE_ENUMERATION_WITH_INDEPENDENT_ORACLE", "CHECKED_PROOF"),
    "stateful": ("FINITE_ENUMERATION_WITH_INDEPENDENT_ORACLE", "CHECKED_PROOF"),
    "high_assurance": ("CHECKED_PROOF",),
}


def numerical_oracle(requested, balance, active):
    if not active or requested == 0:
        return False
    return requested in range(1, balance + 1)


def state_oracle(capacity, old, seats, observed):
    if old > capacity or seats < 1:
        return False
    remaining_seats = set(range(old, capacity))
    return len(remaining_seats) >= seats and observed == old + seats


def compare(population, reference, candidate):
    mismatches = []
    for observation in population:
        expected, actual = reference(*observation), candidate(*observation)
        if expected != actual:
            mismatches.append({"observation": observation, "source_accepts": expected,
                               "candidate_accepts": actual})
    return {"rows": len(population), "mismatch_count": len(mismatches),
            "first_mismatch": next(iter(mismatches), None)}


def admit_evidence(comparison, evidence_kind, policy, *, independent):
    if comparison is None:
        return "UNKNOWN_UNSUPPORTED"
    if comparison["mismatch_count"]:
        return "NEEDS_REVISION"
    effective_kind = ("FINITE_ENUMERATION_WITH_INDEPENDENT_ORACLE"
                      if evidence_kind == "FINITE_ENUMERATION" and independent else evidence_kind)
    return ("EVIDENCE_ELIGIBLE_FOR_REVIEW" if effective_kind in POLICIES[policy]
            else "INSUFFICIENT_EVIDENCE_FOR_POLICY")


def main():
    corpus = ROUNDTRIP / "corpus.json"
    original = json.loads(corpus.read_text())["clauses"]
    by_id = {c["id"]: c for c in original}
    omitted = {"deadline": by_id["deadline"]}
    numeric = tuple(product(range(6), range(6), (False, True)))
    state = tuple(product(range(5), range(6), range(5), range(6)))
    cases = {
        "temporal": (
            TEMPORAL.TRACES, lambda *row: TEMPORAL.independently_expected(row),
            lambda *row: TEMPORAL.allows(by_id, row),
            lambda *row: TEMPORAL.allows(omitted, row),
        ),
        "numeric_precondition": (
            numeric, numerical_oracle,
            lambda requested, balance, active: active and 0 < requested <= balance,
            lambda requested, balance, active: active and 0 <= requested <= balance,
        ),
        "state_transition": (
            state, state_oracle,
            lambda capacity, old, seats, observed:
                seats > 0 and observed == old + seats and observed <= capacity,
            lambda capacity, old, seats, observed:
                seats > 0 and observed == old + seats and seats <= capacity,
        ),
    }
    results = {}
    # At each capacity c and request r in 1..c, exactly 5-c old values exceed
    # capacity after addition while staying in the admitted observation range.
    invalid_capacity_rows = sum(c * (5 - c) for c in range(1, 5))
    expected_counts = {"temporal": (484, 110), "numeric_precondition": (72, 6),
                       "state_transition": (900, invalid_capacity_rows)}
    for name, (population, oracle, compliant, mutant) in cases.items():
        good = compare(population, oracle, compliant)
        bad = compare(population, oracle, mutant)
        assert good["mismatch_count"] == 0
        assert (good["rows"], bad["mismatch_count"]) == expected_counts[name], (name, good, bad)
        results[name] = {
            "comparison": good, "mutant": bad,
            "policy_results": {policy: admit_evidence(good, "FINITE_ENUMERATION", policy, independent=True)
                               for policy in POLICIES},
            "mutant_policy_results": {policy: admit_evidence(bad, "FINITE_ENUMERATION", policy, independent=True)
                                      for policy in POLICIES},
            "without_independent_oracle": admit_evidence(good, "FINITE_ENUMERATION", "stateful", independent=False),
        }
        assert results[name]["policy_results"] == {
            "routine": "EVIDENCE_ELIGIBLE_FOR_REVIEW",
            "stateful": "EVIDENCE_ELIGIBLE_FOR_REVIEW",
            "high_assurance": "INSUFFICIENT_EVIDENCE_FOR_POLICY",
        }
        assert set(results[name]["mutant_policy_results"].values()) == {"NEEDS_REVISION"}
        assert results[name]["without_independent_oracle"] == "INSUFFICIENT_EVIDENCE_FOR_POLICY"
    results["unbounded_liveness"] = {
        "comparison": None,
        "reason": "finite observations do not establish eventual completion over unrestricted traces",
        "policy_results": {policy: admit_evidence(None, "NONE", policy, independent=False)
                           for policy in POLICIES},
    }
    paths = (Path(__file__), ROUNDTRIP / "run.py", corpus)
    return {"schema": "llmlang-rt02-requirement-class-coverage/1", "python": platform.python_version(),
            "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            "synthetic_risk_policies": POLICIES, "results": results}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
