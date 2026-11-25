"""Compare discovery and immutable dependency lock replay across catalog snapshots."""

from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
from itertools import permutations, product
import json
from pathlib import Path
import platform


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


SPEC = digest(["leaf", "contract-1"])
NEXT_SPEC = digest(["leaf", "contract-2"])


@dataclass(frozen=True)
class Provider:
    stable: str
    release: tuple[int, int]
    spec: str
    implementation: str
    capability: str
    accepted: bool


def leaf(minor, specification=SPEC, *, capability="local", accepted=True, body="normal"):
    return Provider("leaf", (1, minor), specification, digest(["leaf", minor, specification, body]),
                    capability, accepted)


L0 = leaf(0)
L1 = leaf(1)
L2 = leaf(2, capability="network")
L3 = leaf(3, NEXT_SPEC)
L4 = leaf(4, accepted=False)
DUPLICATE = leaf(1, body="different same-release bytes")

CATALOGS = {
    "initial": (L0, L1, L2, L3, L4),
    "retired_old": (L1, L2, L3, L4),
    "forked_label": (L0, L1, DUPLICATE, L2),
    "lost_leaf": (),
    "incompatible_only": (L3,),
    "unaccepted_only": (L4,),
    "new_release": (L0, L1, L2, L3, L4, leaf(5)),
}
ROOT = "fixture-consumers"
RESOLVER = "exact-dependency-lock/v1"


def canonical_catalog(providers):
    return sorted(providers, key=lambda row: (row.stable, row.release, row.implementation))


def catalog_root(catalog):
    return digest([asdict(row) for row in canonical_catalog(catalog)])


def eligible(row, specification, pin, capabilities):
    return (row.stable == "leaf" and row.spec == specification and row.accepted
            and (pin is None or pin == row.implementation) and row.capability in capabilities)


def resolve(catalog, specification, pin, capabilities):
    candidates = [row for row in catalog if eligible(row, specification, pin, capabilities)]
    if not candidates:
        return "unavailable", None
    newest = max(row.release for row in candidates)
    selected = {row for row in candidates if row.release == newest}
    if len(selected) != 1:
        return "ambiguous-release", None
    return "selected", selected.pop()


def oracle(catalog, specification, pin, capabilities):
    # Two consumers have distinct exact obligations for the common leaf.
    iface = {p.implementation for p in catalog if p.spec == specification}
    runtime = {p.implementation for p in catalog if p.accepted and p.capability in capabilities}
    available = iface & runtime if pin is None else iface & runtime & {pin}
    for release in sorted({p.release for p in catalog}, reverse=True):
        rows = {p for p in catalog if p.release == release and p.implementation in available}
        if rows:
            return ("selected", next(iter(rows))) if len(rows) == 1 else ("ambiguous-release", None)
    return "unavailable", None


def request(specification, pin, capabilities):
    return digest({"root": ROOT, "constraint": {"spec": specification, "implementation": pin},
                   "capabilities": sorted(capabilities), "resolver": RESOLVER})


def make_lock(catalog, specification, pin, capabilities):
    status, candidate = resolve(catalog, specification, pin, capabilities)
    if candidate is None:
        return status, None
    return status, {
        "catalog": catalog_root(catalog), "request": request(specification, pin, capabilities),
        "library": candidate.stable, "specification": candidate.spec,
        "implementation": candidate.implementation,
    }


def replay(catalog, lock, specification, pin, capabilities):
    if lock["catalog"] != catalog_root(catalog):
        return "incorrect-snapshot"
    if lock["request"] != request(specification, pin, capabilities):
        return "incorrect-request"
    matches = {row for row in catalog if
               (row.stable, row.spec, row.implementation)
               == (lock["library"], lock["specification"], lock["implementation"])}
    if len(matches) != 1:
        return "missing-exact-provider"
    if not eligible(matches.pop(), specification, pin, capabilities):
        return "provider-ineligible"
    return "replayed"


def check():
    counts = Counter()
    comparisons = 0
    exact_old = L0.implementation
    for (label, providers), spec, pin, capabilities in product(
        CATALOGS.items(), (SPEC, NEXT_SPEC), (None, exact_old, L1.implementation),
        (("local",), ("local", "network"), ())
    ):
        expected = oracle(providers, spec, pin, capabilities)
        status, lock = make_lock(providers, spec, pin, capabilities)
        assert status == expected[0]
        counts[status] += 1
        for ordered in permutations(providers):
            assert resolve(ordered, spec, pin, capabilities) == expected
            assert make_lock(ordered, spec, pin, capabilities) == (status, lock)
            if lock is not None:
                assert lock["implementation"] == expected[1].implementation
                assert replay(ordered, lock, spec, pin, capabilities) == "replayed"
            comparisons += 1

    catalog = CATALOGS["initial"]
    later = CATALOGS["new_release"]
    local = ("local",)
    _, old = make_lock(catalog, SPEC, None, local)
    _, latest = make_lock(later, SPEC, None, local)
    controls = {
        "retained_snapshot": replay(catalog, old, SPEC, None, local),
        "new_snapshot_with_old_lock": replay(later, old, SPEC, None, local),
        "changed_capabilities": replay(catalog, old, SPEC, None, ("local", "network")),
        "different_body_same_version_label": replay(catalog, {**old, "implementation": DUPLICATE.implementation},
                                                   SPEC, None, local),
        "unknown_contract": resolve(catalog, digest("unknown"), None, local)[0],
        "fresh_resolution_selects_newer_body": old["implementation"] != latest["implementation"],
        "forked_label_without_body_pin": resolve(CATALOGS["forked_label"], SPEC, None, local)[0],
        "forked_label_with_body_pin": resolve(CATALOGS["forked_label"], SPEC, L1.implementation, local)[0],
    }
    assert controls == {"retained_snapshot": "replayed", "new_snapshot_with_old_lock": "incorrect-snapshot",
                        "changed_capabilities": "incorrect-request",
                        "different_body_same_version_label": "missing-exact-provider",
                        "unknown_contract": "unavailable", "fresh_resolution_selects_newer_body": True,
                        "forked_label_without_body_pin": "ambiguous-release",
                        "forked_label_with_body_pin": "selected"}
    return {"python": platform.python_version(), "resolver": RESOLVER, "profiles": counts,
            "order_comparisons": comparisons, "controls": controls,
            "catalogs": {name: catalog_root(rows) for name, rows in CATALOGS.items()},
            "example_exact_locks": [old, latest],
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(check(), sort_keys=True, indent=2))
