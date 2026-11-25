"""Check mirrored delivery, independent retention and exact collection generations."""

from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform


HERE = Path(__file__).resolve().parent
PINS = {
    "DECLARED-PACKAGE-RIGHTS-01": "96cd6a2a14deed87811b3c01107bf6630947e84068ac4d3ad88d02cb499f5611",
    "REACHABILITY-SWEEP-01": "c52f2d38ae209f1c9af6af7dfa664d1039d192c9a033f8c0fa65149b1bae574e",
}


def evidence():
    for name, pinned in PINS.items():
        assert sha256((HERE.parent / name / "evidence.json").read_bytes()).hexdigest() == pinned


@dataclass(frozen=True)
class Publication:
    root: str
    archive: str
    epoch: int
    current: bool
    verified: bool


@dataclass(frozen=True)
class Rights:
    root: str
    principal: str
    operation: str
    epoch: int
    verified: bool


@dataclass(frozen=True)
class Retention:
    generation: int
    leases: frozenset[str]
    retains_audit: bool
    local_payload: bool


def delivery(publication, rights, current_epoch, mirrored_archive, principal):
    if not publication.current or not publication.verified or publication.epoch != current_epoch:
        return "publication-unavailable"
    if publication.archive != mirrored_archive:
        return "archive-mismatch"
    if rights != Rights(publication.root, principal, "deliver", current_epoch, True):
        return "permission-unavailable"
    return "deliver"


def collection(publication, retained, plan_generation):
    if retained.generation != plan_generation:
        return "retry-mark", retained
    if publication.current or retained.leases or retained.retains_audit:
        return "retained", retained
    if not retained.local_payload:
        return "already-absent", retained
    return "collected", replace(retained, generation=retained.generation + 1, local_payload=False)


def history_access(retained, principal, approval):
    return retained.local_payload and approval and principal in retained.leases


def collect():
    evidence()
    baseline_pub = Publication("package-a", "exact-zip-a", 7, True, True)
    baseline_rights = Rights("package-a", "reader-a", "deliver", 7, True)
    delivery_counts = Counter()
    for live, pub_verified, pub_fresh, archive, right, allowed_principal, rights_fresh in product(
        (False, True), (False, True), (False, True), ("exact-zip-a", "repacked-zip-a"),
        ("none", "verified", "other-root", "inspect"), ("reader-a", "reader-b"), (False, True)
    ):
        published = replace(baseline_pub, current=live, verified=pub_verified, epoch=7 if pub_fresh else 6)
        claims = replace(baseline_rights, verified=right != "none", epoch=7 if rights_fresh else 6,
                         root="other" if right == "other-root" else "package-a",
                         operation="inspect" if right == "inspect" else "deliver")
        observed = delivery(published, claims, 7, archive, allowed_principal)
        accepted = (live and pub_verified and pub_fresh and archive == "exact-zip-a"
                    and right == "verified" and allowed_principal == "reader-a" and rights_fresh)
        assert (observed == "deliver") == accepted
        delivery_counts[observed] += 1

    collection_counts = Counter()
    for live, leases, audit, payload, exact_plan in product(
        (False, True), (frozenset(), frozenset({"reader-a"}), frozenset({"reader-a", "reader-b"})),
        (False, True), (False, True), (False, True)
    ):
        retained = Retention(19, leases, audit, payload)
        result, after = collection(replace(baseline_pub, current=live), retained, 19 if exact_plan else 18)
        can_remove = exact_plan and not (live or leases or audit) and payload
        assert (result == "collected") is bool(can_remove)
        assert after == (Retention(20, leases, audit, False) if can_remove else retained)
        collection_counts[result] += 1

    historical = Retention(19, frozenset({"reader-a"}), False, True)
    revoked = replace(baseline_pub, current=False)
    controls = {
        "revoked_exact_mirror": delivery(revoked, baseline_rights, 7, "exact-zip-a", "reader-a"),
        "historical_reader_with_lease": history_access(historical, "reader-a", True),
        "historical_reader_without_approval": history_access(historical, "reader-a", False),
        "historical_reader_without_lease": history_access(historical, "reader-b", True),
        "revoked_with_lease": collection(revoked, historical, 19)[0],
        "drop_last_lease_requires_remark": collection(revoked, replace(historical, generation=20, leases=frozenset()), 19)[0],
        "refreshed_collection_after_release": collection(revoked, replace(historical, generation=20, leases=frozenset()), 20)[0],
        "fresh_signature_for_repacked_archive": delivery(replace(baseline_pub, archive="repacked-zip-a"),
                                                         baseline_rights, 7, "repacked-zip-a", "reader-a"),
    }
    assert controls == {
        "revoked_exact_mirror": "publication-unavailable",
        "historical_reader_with_lease": True,
        "historical_reader_without_approval": False,
        "historical_reader_without_lease": False,
        "revoked_with_lease": "retained",
        "drop_last_lease_requires_remark": "retry-mark",
        "refreshed_collection_after_release": "collected",
        "fresh_signature_for_repacked_archive": "deliver",
    }
    return {"python": platform.python_version(), "delivery": delivery_counts, "collection": collection_counts,
            "controls": controls, "native_evidence_sha256": PINS,
            "sources_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(collect(), sort_keys=True, indent=2))
