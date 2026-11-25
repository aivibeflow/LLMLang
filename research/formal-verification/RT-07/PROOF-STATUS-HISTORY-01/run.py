#!/usr/bin/env python3
"""Replay finite receipt arrivals and compare history-based and last-arrival status."""

from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
from itertools import combinations, permutations
import json
from pathlib import Path
import platform

HERE = Path(__file__).resolve().parent
SUBJECT = "claim-v2"
INCOMPLETE = frozenset({"unknown", "rejected"})


@dataclass(frozen=True)
class Receipt:
    attempt: str
    subject: str
    verdict: str
    authorized: bool = True


@dataclass(frozen=True)
class Evidence:
    checked_proof: bool = False
    checked_counterexample: bool = False
    incomplete_attempt: bool = False

    def merge(self, other):
        return Evidence(self.checked_proof or other.checked_proof,
                        self.checked_counterexample or other.checked_counterexample,
                        self.incomplete_attempt or other.incomplete_attempt)

    def project(self, open_premise):
        if self.checked_counterexample:
            return "conflict" if self.checked_proof and not open_premise else "refuted"
        if self.checked_proof:
            return "checked" if open_premise else "proven"
        return "unknown" if self.incomplete_attempt else "candidate"


ATTEMPTS = (
    Receipt("draft", SUBJECT, "candidate"),
    Receipt("timeout", SUBJECT, "unknown"),
    Receipt("backend-unknown", SUBJECT, "unknown"),
    Receipt("rejected-proof", SUBJECT, "rejected"),
    Receipt("checked-proof", SUBJECT, "proof"),
    Receipt("checked-witness", SUBJECT, "counterexample"),
    Receipt("old-proof", "claim-v1", "proof"),
    Receipt("untrusted-proof", SUBJECT, "proof", authorized=False),
)


def summarize(history, open_premise):
    seen = {}
    for receipt in history:
        seen.setdefault(receipt.attempt, set()).add(receipt)
    if any(len(receipts) > 1 for receipts in seen.values()):
        return "receipt-conflict", seen

    evidence = Evidence()
    for (receipt,) in seen.values():
        if receipt.subject != SUBJECT or not receipt.authorized:
            continue
        verdict = receipt.verdict
        evidence = evidence.merge(Evidence(verdict == "proof", verdict == "counterexample",
                                           verdict in INCOMPLETE))
    return evidence.project(open_premise), seen


def set_oracle(receipts, open_premise):
    kinds = {receipt.verdict for receipt in receipts if receipt.subject == SUBJECT and receipt.authorized}
    if {"proof", "counterexample"} <= kinds:
        return "refuted" if open_premise else "conflict"
    if "counterexample" in kinds:
        return "refuted"
    if "proof" in kinds:
        return "checked" if open_premise else "proven"
    if kinds & INCOMPLETE:
        return "unknown"
    return "candidate"


def last_arrival(history, open_premise):
    latest = next((receipt for receipt in reversed(history)
                   if receipt.subject == SUBJECT and receipt.authorized), None)
    if latest is None:
        return "candidate"
    return {
        "candidate": "candidate", "rejected": "unknown", "unknown": "unknown",
        "proof": "checked" if open_premise else "proven", "counterexample": "refuted",
    }[latest.verdict]


def run():
    counts = Counter()
    statuses = Counter()
    witnesses = {}
    comparison = sha256()
    for size in range(5):
        for subset in combinations(ATTEMPTS, size):
            for open_premise in (False, True):
                counts["subset_premise_pairs"] += 1
                ordered_statuses = set()
                expected = set_oracle(subset, open_premise)
                expected_attempts = {receipt.attempt: {receipt} for receipt in subset}
                for history in permutations(subset):
                    actual, exact_history = summarize(history, open_premise)
                    latest = last_arrival(history, open_premise)
                    if actual != expected or exact_history != expected_attempts:
                        raise AssertionError((history, open_premise, actual, expected))
                    statuses[actual] += 1
                    ordered_statuses.add(latest)
                    counts["ordered_profiles"] += 1
                    counts["last_arrival_differs"] += actual != latest
                    counts["closed_proof_demoted_to_unresolved"] += (
                        actual == "proven" and latest in ("unknown", "candidate")
                    )
                    if actual != latest:
                        witnesses.setdefault(f"{actual}:{latest}", {
                            "arrivals": [item.attempt for item in history],
                            "open_premise": open_premise,
                        })
                    row = ([item.attempt for item in history], open_premise, actual, latest)
                    comparison.update(json.dumps(row, separators=(",", ":")).encode("ascii") + b"\n")
                counts["order_sensitive_last_arrival_pairs"] += len(ordered_statuses) > 1

    proof = ATTEMPTS[4]
    conflicting = Receipt(proof.attempt, SUBJECT, "counterexample")
    if summarize((proof, proof), False) != ("proven", {proof.attempt: {proof}}):
        raise AssertionError("An exact repeat changed the evidence history")
    for arrival in ((proof, conflicting), (conflicting, proof)):
        if summarize(arrival, False) != ("receipt-conflict", {proof.attempt: {proof, conflicting}}):
            raise AssertionError("A conflicting receipt identity was accepted")
    timeouts = (ATTEMPTS[1], ATTEMPTS[2])
    status, distinct = summarize(timeouts, False)
    if status != "unknown" or len(distinct) != 2:
        raise AssertionError("Distinct attempts were collapsed into a status label")
    return {
        "schema": "llmlang-proof-status-history/1", "python": platform.python_version(),
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("Status.lean", "run.py", "axioms.txt")},
        "attempt_templates": [asdict(receipt) for receipt in ATTEMPTS],
        "counts": counts, "history_based_status_counts": statuses,
        "additional_controls": {"exact_repeat_keeps_one_attempt": True,
                                "conflicting_receipt_in_both_orders": True,
                                "same_status_distinct_attempt_count": len(distinct)},
        "comparison_rows_sha256": comparison.hexdigest(),
        "disagreement_witnesses": witnesses,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
