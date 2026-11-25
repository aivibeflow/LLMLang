"""Compare stale and selected callee evidence for a fixed caller body."""

from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform


CALLER_BODY = "callee(input)+fee"
PROFILES = ("caller-body-only", "exact-callee")
HERE = Path(__file__).resolve().parent


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Receipt:
    provider: str
    semantics: str
    bound: int


def provider_id(ceiling):
    return digest(["clamped-helper", ceiling])


def decide(current, receipt, fee, limit, profile):
    if receipt is None:
        return "unknown"
    if profile == "exact-callee" and (current, "nat-bound-v1") != (receipt.provider, receipt.semantics):
        return "unknown"
    return "accept" if receipt.bound + fee <= limit else "refuse"


def run():
    totals = {profile: Counter() for profile in PROFILES}
    false_accepts = Counter()
    declined_good = Counter()
    body = digest(CALLER_BODY)
    checks = 0
    for old, current, fee, limit, available in product(range(9), range(9), range(5), range(13), (False, True)):
        old_receipt = Receipt(provider_id(old), "nat-bound-v1", old) if available else None
        current_receipt = Receipt(provider_id(current), "nat-bound-v1", current)
        oracle = all(min(value, current) + fee <= limit for value in range(17))
        verdicts = {
            "caller-body-only": decide(provider_id(current), old_receipt, fee, limit, "caller-body-only"),
            "exact-callee": decide(provider_id(current), old_receipt, fee, limit, "exact-callee"),
        }
        for profile, outcome in verdicts.items():
            totals[profile][outcome] += 1
            if outcome == "accept" and not oracle:
                false_accepts[profile] += 1
            if outcome == "refuse" and oracle:
                declined_good[profile] += 1
        if available and old == current:
            assert verdicts["exact-callee"] == ("accept" if oracle else "refuse")
        else:
            assert verdicts["exact-callee"] == "unknown"
        assert decide(provider_id(current), current_receipt, fee, limit, "exact-callee") == (
            "accept" if oracle else "refuse")
        checks += 1
    assert not false_accepts["exact-callee"] and not declined_good["exact-callee"]
    old = Receipt(provider_id(2), "nat-bound-v1", 2)
    const = (provider_id(5), old, 1, 3)
    controls = {
        "old_receipt_unbound": decide(*const, "caller-body-only"),
        "old_receipt_exact": decide(*const, "exact-callee"),
        "new_checked_receipt": decide(provider_id(5), Receipt(provider_id(5), "nat-bound-v1", 5),
                                      1, 3, "exact-callee"),
        "wrong_semantic_profile": decide(provider_id(2), replace(old, semantics="different"),
                                         1, 3, "exact-callee"),
    }
    assert controls == {"old_receipt_unbound": "accept", "old_receipt_exact": "unknown",
                        "new_checked_receipt": "refuse", "wrong_semantic_profile": "unknown"}
    return {"python": platform.python_version(), "checks_per_gate": checks, "caller_body": body,
            "totals": totals, "false_accepts": {name: false_accepts[name] for name in PROFILES},
            "false_refusals": {name: declined_good[name] for name in PROFILES}, "controls": controls,
            "sources": {name: sha256((HERE / name).read_bytes()).hexdigest()
                        for name in ("check.py", "Bounds.lean", "axioms.txt")}}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
