"""Check defensive cache eligibility after changed authority and independent rechecks."""

from collections import Counter
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
import platform


NODES = (
    "compiler-a", "compiler-b", "checker-a", "checker-b",
    "implementation-a", "implementation-b", "proof-a", "proof-b", "result", "dependent",
)
PAYLOADS = ("implementation-a", "implementation-b", "result")
ROOTS = frozenset(("compiler-a", "compiler-b", "checker-a", "checker-b"))


def supports(rebuild, recheck):
    return {
        "implementation-a": (("compiler-a",),),
        "implementation-b": (("compiler-b",),) if rebuild else (),
        "proof-a": (("checker-a", "implementation-a"),),
        "proof-b": (("checker-b", "implementation-b"),) if recheck else (),
        "result": (("implementation-a", "proof-a"), ("implementation-b", "proof-b")),
        "dependent": (("result",),),
    }


def settle(requirements, revoked, verified_bytes):
    admitted = {base for base in ROOTS if base not in revoked}
    progress = True
    while progress:
        progress = False
        for name, alternatives in requirements.items():
            if name in admitted or name in revoked or (name in PAYLOADS and name not in verified_bytes):
                continue
            if any(set(facts) <= admitted for facts in alternatives):
                admitted.add(name)
                progress = True
    return admitted


def receipt_scope(generation, requirements, revoked, verified_bytes):
    context = {"generation": generation, "requirements": requirements,
               "revoked": sorted(revoked), "verified_bytes": sorted(verified_bytes)}
    data = json.dumps(context, sort_keys=True, separators=(",", ":")).encode()
    return sha256(data).hexdigest()


def finite_check():
    revocable = (*sorted(ROOTS), "implementation-a", "implementation-b")
    mixtures = [frozenset(group) for size in range(3) for group in combinations(revocable, size)]
    outcomes = Counter()
    comparisons = 0
    for revoked, rebuild, recheck, bytes_verified in product(mixtures, (False, True), (False, True),
                                                            product((False, True), repeat=len(PAYLOADS))):
        verified = {name for name, present in zip(PAYLOADS, bytes_verified, strict=True) if present}
        current = settle(supports(rebuild, recheck), revoked, verified)
        path_a = all(name not in revoked for name in ("compiler-a", "checker-a", "implementation-a"))
        path_b = rebuild and recheck and all(
            name not in revoked for name in ("compiler-b", "checker-b", "implementation-b"))
        acceptable = ("result" in verified and ((path_a and "implementation-a" in verified)
                                                  or (path_b and "implementation-b" in verified)))
        assert ("result" in current) == ("dependent" in current) == acceptable
        outcomes["eligible" if acceptable else "unavailable"] += 1
        comparisons += 1

    exact = set(PAYLOADS)
    removed = {"compiler-a"}
    original = settle(supports(False, False), set(), exact)
    after = settle(supports(False, False), removed, exact)
    rebuilt = settle(supports(True, False), removed, exact)
    validated = settle(supports(True, True), removed, exact)
    broken = settle(supports(True, True), removed, exact - {"result"})
    cyclic = settle({"result": (("dependent",),), "dependent": (("result",),)}, set(), exact)
    controls = {
        "original_eligible": "result" in original,
        "unavailable_after_compromise": "result" not in after and "dependent" not in after,
        "rebuild_only_insufficient": "implementation-b" in rebuilt and "result" not in rebuilt,
        "independent_recheck_recovers": "proof-b" in validated and "dependent" in validated,
        "delivery_bytes_required": "result" not in broken and "dependent" not in broken,
        "restored_eligibility_requires_new_view_receipt": (
            receipt_scope(1, supports(False, False), set(), exact)
            != receipt_scope(2, supports(True, True), removed, exact)),
        "unsupported_cycle_refused": "result" not in cyclic and "dependent" not in cyclic,
    }
    assert all(controls.values())
    revoked_node = {"implementation-a"}
    assert "result" not in settle(supports(False, False), revoked_node, exact)
    assert "result" in settle(supports(True, True), revoked_node, exact)
    return {"python": platform.python_version(), "comparisons": comparisons, "outcomes": outcomes,
            "nodes": NODES, "controls": controls,
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(finite_check(), sort_keys=True, indent=2))
