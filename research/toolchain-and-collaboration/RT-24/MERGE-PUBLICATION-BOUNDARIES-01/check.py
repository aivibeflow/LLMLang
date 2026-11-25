"""Check scoped merge evidence, retained alternatives and replay identity."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess


BASE = "0e77a0690cee79d72cddf89e5678fec75fb42f07"
RT24 = "research/toolchain-and-collaboration/RT-24"
REQUIRED = ("graph", "types", "contracts", "dependencies", "tests", "proofs")
PINS = ("base", "left", "right")
OPTIONS = ("none", "exact-resolver", "stale-resolver", "ungranted-resolver")


def audit(pins, candidate, validation, policy, choice, status):
    preimage = [pins, candidate, sorted(validation.items()), policy, choice, status]
    return sha256(json.dumps(preimage, separators=(",", ":")).encode()).hexdigest()


def qualify(independent, choice, validation):
    if choice in {"stale-resolver", "ungranted-resolver"}:
        return "unverified-resolution"
    if not independent and choice == "none":
        return "conflict"
    if "refuted" in validation.values():
        return "invalid"
    if any(validation.get(step) != "verified" for step in REQUIRED):
        return "pending-validation"
    return "eligible"


def check():
    totals = Counter()
    candidates = 0
    for independent, choice, states in product((False, True), OPTIONS,
                                                product(("verified", "missing", "refuted"), repeat=6)):
        validation = dict(zip(REQUIRED, states, strict=True))
        candidate = "synthesized" if choice == "exact-resolver" else "automatic"
        disposition = qualify(independent, choice, validation)
        lookup = {
            "stale-resolver": "unverified-resolution",
            "ungranted-resolver": "unverified-resolution",
            "none": None if independent else "conflict",
            "exact-resolver": None,
        }
        expected = lookup[choice]
        if expected is None:
            expected = {"refuted": "invalid", "missing": "pending-validation",
                        "verified": "eligible"}[max(states, key=("verified", "missing", "refuted").index)]
        assert disposition == expected
        receipt = audit(PINS, candidate, validation, "policy-v1", choice, disposition)
        assert receipt == audit(PINS, candidate, dict(reversed(tuple(validation.items()))), "policy-v1", choice,
                                disposition)
        assert receipt != audit((PINS[0], PINS[2], PINS[1]), candidate, validation, "policy-v1", choice, disposition)
        assert receipt != audit(PINS, candidate, validation, "policy-v2", choice, disposition)
        if disposition == "eligible":
            candidates += 1
        else:
            assert receipt != audit(PINS[:1], candidate, validation, "policy-v1", choice, disposition)
        totals[disposition] += 1

    incomplete = dict.fromkeys(REQUIRED[:-1], "verified")
    assert qualify(True, "none", incomplete) == "pending-validation"
    return {"outcomes": dict(totals), "cases": sum(totals.values()), "eligible": candidates}


def prior():
    result = {}
    for name in ("INDEPENDENT-MERGE-01", "CONSERVATIVE-MERGE-01", "MERGE-RESOLUTION-BOUNDARY-01",
                 "MERGE-COVERAGE-01", "MERGE-AUDIT-REPLAY-01"):
        path = f"{RT24}/{name}/evidence.json"
        raw = subprocess.check_output(["git", "show", f"{BASE}:{path}"])
        result[name] = sha256(raw).hexdigest()
    return result


if __name__ == "__main__":
    print(json.dumps({
        "baseline": BASE, "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "prior_evidence": prior(), "matrix": check(),
    }, sort_keys=True, indent=2))
