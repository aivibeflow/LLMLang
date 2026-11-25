"""Check reproducible binding decisions and their separate publication conditions."""

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from itertools import product
import json
from pathlib import Path


@dataclass(frozen=True)
class Receipt:
    provider: str
    snapshot: str
    independently_checked: bool
    refuted: bool


PROVIDERS = ("provider-a", "provider-b")
CURRENT = "required-snapshot"
STATUSES = ("exact", "refuted", "stale", "unchecked")


def verification(provider, receipt):
    if (receipt.provider, receipt.snapshot) != (provider, CURRENT) or not receipt.independently_checked:
        return "unknown"
    return "excluded" if receipt.refuted else "eligible"


def resolve(receipts, choice, complete):
    if not complete:
        return "pending", None
    observed = {provider: verification(provider, receipt) for provider, receipt in receipts}
    if len(receipts) != len(observed) or set(observed) != set(PROVIDERS) or "unknown" in observed.values():
        return "pending", None
    candidates = {provider for provider, verdict in observed.items() if verdict == "eligible"}
    if choice is not None:
        return ("bound", choice) if choice in candidates else ("choice-refused", None)
    if len(candidates) == 1:
        return "bound", next(iter(candidates))
    return ("ambiguous" if candidates else "no-match"), None


def receipt_for(provider, status):
    return Receipt(provider, CURRENT if status != "stale" else "prior",
                   status != "unchecked", status == "refuted")


def expected(first, second, choice, complete):
    if not complete or first in {"stale", "unchecked"} or second in {"stale", "unchecked"}:
        return "pending", None
    if choice is not None:
        accepted = first if choice == PROVIDERS[0] else second
        return ("bound", choice) if accepted == "exact" else ("choice-refused", None)
    outcomes = {
        ("exact", "exact"): ("ambiguous", None),
        ("exact", "refuted"): ("bound", PROVIDERS[0]),
        ("refuted", "exact"): ("bound", PROVIDERS[1]),
        ("refuted", "refuted"): ("no-match", None),
    }
    return outcomes[first, second]


def run():
    resolution = Counter()
    publication = Counter()
    for first, second, explicit, complete in product(STATUSES, STATUSES, (None, *PROVIDERS), (True, False)):
        receipts = tuple(zip(PROVIDERS, (receipt_for(PROVIDERS[0], first),
                                        receipt_for(PROVIDERS[1], second)), strict=True))
        decision = resolve(receipts, explicit, complete)
        assert decision == resolve(tuple(reversed(receipts)), explicit, complete)
        assert decision == expected(first, second, explicit, complete)
        resolution[decision[0]] += 1
        for authorized, current, caller in product((True, False), repeat=3):
            staged = decision[1] if decision[0] == "bound" and authorized and current else None
            runtime_claim = staged if caller and staged else None
            assert bool(runtime_claim) == all((authorized, current, caller, decision[0] == "bound"))
            publication["published" if staged else "withheld"] += 1
            caller_status = "closed-caller" if runtime_claim else "conditional-caller" if caller else "unavailable-caller"
            publication[caller_status] += 1
    assert resolve(((PROVIDERS[0], receipt_for(PROVIDERS[0], "exact")),), None, True) == ("pending", None)
    exact = tuple((provider, receipt_for(provider, "exact")) for provider in PROVIDERS)
    assert resolve((*exact, exact[0]), None, True) == ("pending", None)
    foreign = receipt_for("other-provider", "exact")
    assert verification(PROVIDERS[0], foreign) == "unknown"
    return {
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "resolution_cases": sum(resolution.values()), "resolution_counts": dict(resolution),
        "publication_cases": sum(resolution.values()) * 8, "publication_counts": dict(publication),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
