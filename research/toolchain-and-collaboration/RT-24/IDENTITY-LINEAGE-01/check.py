"""Check versioned identity lineage and exact caller rebinding in a finite fixture."""

from collections import Counter
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform


def digest(domain, value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256(domain.encode() + b"\0" + raw).hexdigest()


@dataclass(frozen=True)
class Entity:
    stable: str
    label: str
    public_name: str
    behavior: str

    @property
    def op(self):
        return digest("operation", [self.public_name, self.behavior])


OLD = {
    "shared": Entity("shared", "Shared operation", "reserve", "combined-v1"),
    "second": Entity("second", "Other operation", "lookup", "other-v1"),
}
CALLS = {"legacy": "shared", "modern": "shared", "other": "second"}
NEXT = {
    "rename-display": {**OLD, "shared": replace(OLD["shared"], label="New display label")},
    "rename-public": {**OLD, "shared": replace(OLD["shared"], public_name="reserve_new")},
    "split": {"left": Entity("left", "Left", "reserve_legacy", "legacy-v1"),
              "right": Entity("right", "Right", "reserve_modern", "modern-v1"),
              "second": OLD["second"]},
    "merge": {"merged": Entity("merged", "Merged", "combined", "merged-v1")},
}
AUTHORIZED = {
    "rename-display": CALLS,
    "rename-public": CALLS,
    "split": {"legacy": "left", "modern": "right", "other": "second"},
    "merge": {caller: "merged" for caller in CALLS},
}
LINEAGE = {
    "rename-display": (("shared", "shared"),),
    "rename-public": (("shared", "shared"),),
    "split": (("shared", "left"), ("shared", "right")),
    "merge": (("shared", "merged"), ("second", "merged")),
}


def snapshot(entities):
    return digest("selected-snapshot", {key: asdict(value) for key, value in entities.items()})


def required_evidence(caller, target):
    return digest("call-rebind-evidence", [caller, OLD[CALLS[caller]].op, target.op, target.stable])


def navigate(kind, target, proposed, lineage, evidence, old_snapshot, new_snapshot):
    expected_target = NEXT[kind]
    if (old_snapshot, new_snapshot) != (snapshot(OLD), snapshot(expected_target)):
        return "unbound-snapshot"
    if snapshot(target) != new_snapshot or tuple(sorted(lineage)) != tuple(sorted(LINEAGE[kind])):
        return "invalid-lineage"
    if set(proposed) != set(CALLS):
        return "incomplete-callers"
    if proposed != AUTHORIZED[kind]:
        return "unauthorized-route"
    for caller, destination in proposed.items():
        prior, current = OLD[CALLS[caller]], target[destination]
        if (prior.op != current.op or prior.stable != current.stable) and (
                required_evidence(caller, current) not in evidence):
            return "missing-rebind-evidence"
    return "accepted"


def measure():
    outcomes = Counter()
    samples = {}
    prior = snapshot(OLD)
    assert NEXT["rename-display"]["shared"].op == OLD["shared"].op
    assert NEXT["rename-public"]["shared"].op != OLD["shared"].op
    duplicate = Entity("clone", "Independent", OLD["shared"].public_name, OLD["shared"].behavior)
    assert duplicate.op == OLD["shared"].op and duplicate.stable != OLD["shared"].stable
    for kind, target in NEXT.items():
        projected = snapshot(target)
        selected = AUTHORIZED[kind]
        complete = {required_evidence(caller, target[destination])
                    for caller, destination in selected.items()}
        suite = Counter()
        for destinations, supplied, consistent_lineage, consistent_snapshot, complete_inventory in product(
            product(target, repeat=len(CALLS)), (False, True), (False, True), (False, True), (False, True)
        ):
            routes = dict(zip(CALLS, destinations, strict=True))
            if not complete_inventory:
                routes.pop("other")
            result = navigate(kind, target, routes, LINEAGE[kind] if consistent_lineage else (),
                              complete if supplied else set(), prior if consistent_snapshot else projected,
                              projected)
            expected = (consistent_lineage and consistent_snapshot and complete_inventory
                        and routes == selected and (supplied or kind == "rename-display"))
            assert (result == "accepted") == expected, (kind, result, routes)
            suite[result] += 1
            outcomes[result] += 1
        samples[kind] = {"snapshot": projected, "entities": dict(sorted((k, v.op) for k, v in target.items())),
                         "lineage": LINEAGE[kind], "results": suite}
    stale = navigate("split", NEXT["split"], AUTHORIZED["split"], LINEAGE["split"],
                     {required_evidence("legacy", NEXT["split"]["left"])}, prior, snapshot(NEXT["split"]))
    assert stale == "missing-rebind-evidence"
    renamed = NEXT["rename-display"]
    same_content_substitute = navigate("rename-display", {**renamed, "shared": duplicate},
                                       CALLS, LINEAGE["rename-display"], set(), prior, snapshot(renamed))
    assert same_content_substitute == "invalid-lineage"
    return {"python": platform.python_version(), "outcomes": outcomes, "total": sum(outcomes.values()),
            "cases": samples, "original_snapshot": prior, "single_caller_receipt_in_split": stale,
            "equal_content_different_stable_id": same_content_substitute,
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(measure(), sort_keys=True, indent=2))
