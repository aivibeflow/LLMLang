#!/usr/bin/env python3
"""Exhaustively compare proof validity, contract feasibility and adequacy."""

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform

HERE = Path(__file__).resolve().parent
DOMAIN = (0, 1)
INPUT_OUTPUT = tuple(product(DOMAIN, repeat=2))
IMPLEMENTATIONS = INPUT_OUTPUT


@dataclass(frozen=True)
class Contract:
    eligibility: int
    postcondition: int

    def eligible(self, value):
        return bool(self.eligibility & (1 << value))

    def permits(self, value, output):
        return bool(self.postcondition & (1 << (2 * value + output)))

    def allows(self, value, output):
        return not self.eligible(value) or self.permits(value, output)

    def satisfies(self, implementation):
        return all(self.allows(value, implementation[value]) for value in DOMAIN)


def run():
    contracts = [Contract(*pair) for pair in product(range(4), range(16))]
    providers = {spec: {implementation for implementation in IMPLEMENTATIONS
                        if spec.satisfies(implementation)} for spec in contracts}
    counts = Counter()
    witnesses = {}
    for candidate, intent in product(contracts, repeat=2):
        checked = providers[candidate]
        intent_providers = providers[intent]
        counts["contract_pairs"] += 1
        counts["candidate_valid_triples"] += len(checked)
        rejected = checked - intent_providers
        counts["candidate_valid_intent_false_triples"] += len(rejected)
        implication = not rejected
        inclusion = all(not candidate.allows(value, output) or intent.allows(value, output)
                        for value, output in INPUT_OUTPUT)
        covers = all(not intent.eligible(value) or candidate.eligible(value) for value in DOMAIN)
        guarantee = all(not intent.eligible(value) or not candidate.permits(value, output)
                        or intent.permits(value, output) for value, output in INPUT_OUTPUT)
        if checked:
            counts["feasible_candidate_pairs"] += 1
            if implication != inclusion:
                raise AssertionError((candidate, intent))
            if not implication:
                counts["feasible_inadequate_pairs"] += 1
                if covers:
                    counts["inadequate_despite_coverage"] += 1
                else:
                    counts["inadequate_and_narrowed"] += 1
            if implication and not covers:
                counts["adequate_without_admission_coverage"] += 1
        else:
            counts["infeasible_vacuous_implication_pairs"] += 1
            if not inclusion:
                counts["infeasible_breaks_pointwise_equivalence"] += 1
        if covers and guarantee and not implication:
            raise AssertionError((candidate, intent, "Coverage plus guarantee is unsound"))

    controls = (
        ("weak_guarantee", Contract(3, 15), Contract(3, 9), (0, 0)),
        ("narrowed_precondition", Contract(1, 9), Contract(3, 9), (0, 0)),
        ("empty_precondition", Contract(0, 0), Contract(3, 9), (0, 0)),
        ("infeasible_contract", Contract(3, 0), Contract(3, 9), None),
        ("adequate_without_coverage", Contract(1, 13), Contract(3, 13), (0, 0)),
    )
    for name, candidate, intent, implementation in controls:
        witnesses[name] = {
            "candidate": (candidate.eligibility, candidate.postcondition),
            "intent": (intent.eligibility, intent.postcondition),
            "implementation": implementation,
            "feasible": bool(providers[candidate]),
            "implementation_satisfies_candidate": None if implementation is None else candidate.satisfies(implementation),
            "implementation_satisfies_intent": None if implementation is None else intent.satisfies(implementation),
            "all_valid_implementations_transfer": providers[candidate] <= providers[intent],
            "eligibility_coverage": candidate.eligibility & intent.eligibility == intent.eligibility,
        }
    expected = {
        "weak_guarantee": (True, True, False, False, True),
        "narrowed_precondition": (True, True, False, False, False),
        "empty_precondition": (True, True, False, False, False),
        "infeasible_contract": (False, None, None, True, True),
        "adequate_without_coverage": (True, True, True, True, False),
    }
    for name, control in witnesses.items():
        actual = tuple(control.values())[3:]
        if actual != expected[name]:
            raise AssertionError((name, actual, expected[name]))

    return {
        "schema": "llmlang-proof-adequacy/1", "python": platform.python_version(),
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "Adequacy.lean", "axioms.txt")},
        "contracts": len(contracts), "total_implementations": len(IMPLEMENTATIONS),
        "counts": counts, "witnesses": witnesses,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
