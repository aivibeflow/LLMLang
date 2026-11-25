"""Compare bare dependency-selection Booleans with exact profile receipts."""

from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
PROTOTYPE = HERE.parents[1] / "PROTOTYPES" / "PACKAGE-INDEX-01"
sys.path.insert(0, str(PROTOTYPE))
from package_closure import ClosureError, resolve_dependency_closure


NAMES = ("app", "linux", "windows", "network", "tls", "logging", "tail", "target-metadata")
HASH = {name: "sha256:" + sha256(name.encode()).hexdigest() for name in NAMES}
POLICIES = ("roots_only", "closure", "closure_with_optional")
ROOTS = (HASH["app"],)


@dataclass(frozen=True)
class Profile:
    target: str
    network: bool
    tls: bool
    logging: bool


@dataclass(frozen=True)
class Receipt:
    snapshot_id: str
    roots: tuple[str, ...]
    policy: str
    profile: Profile
    decisions: tuple[tuple[tuple[str, str], bool], ...]


def dependency(edge_id, kind, target, condition=None):
    row = {"edge_id": edge_id, "kind": kind, "target_hash": HASH[target]}
    if condition is not None:
        row["condition"] = condition
    return row


EDGES = {
    HASH["app"]: (
        dependency("choose-linux", "required", "linux", {"target": "linux"}),
        dependency("choose-windows", "required", "windows", {"target": "windows"}),
        dependency("enable-network", "required", "network", {"feature": "network"}),
        dependency("enable-logging", "optional", "logging", {"feature": "logging"}),
        dependency("optional-linux-alias", "optional", "linux", {"feature": "logging"}),
        dependency("reported-target", "target", "target-metadata"),
    ),
    HASH["network"]: (dependency("enable-tls", "required", "tls", {"feature": "tls"}),),
    HASH["tls"]: (dependency("tls-tail", "required", "tail"),),
    HASH["logging"]: (dependency("logging-tail", "required", "tail"),),
    HASH["tail"]: (dependency("back-to-network", "required", "network"),),
}


class Snapshot:
    def __init__(self, missing):
        self.snapshot_id = f"fixture-without-{missing or 'nothing'}"
        self.objects = {address: {"hash": address, "kind": "function", "size": index + 1}
                        for index, (name, address) in enumerate(HASH.items()) if name != missing}
        self.requests = []

    def get_object(self, content_hash):
        self.requests.append(content_hash)
        return self.objects[content_hash]

    def get_dependencies(self, source_hash):
        return EDGES.get(source_hash, ())


def derive(profile):
    features = {"network": profile.network, "tls": profile.tls, "logging": profile.logging}
    decisions = {}
    for origin, dependencies in EDGES.items():
        for edge in dependencies:
            guard = edge.get("condition")
            if guard is None:
                continue
            if "target" in guard:
                selected = profile.target == guard["target"]
            else:
                selected = features[guard["feature"]]
            decisions[(origin, edge["edge_id"])] = selected
    return tuple(sorted(decisions.items()))


def receipt(snapshot, policy, profile):
    return Receipt(snapshot.snapshot_id, ROOTS, policy, profile, derive(profile))


def resolve(snapshot, policy, values):
    snapshot.requests.clear()
    try:
        resolved = resolve_dependency_closure(ROOTS, snapshot, policy=policy,
                                             condition_values=dict(values))
    except ClosureError as exc:
        if not str(exc).startswith(("missing exact dependency object", "conditional dependency requires")):
            raise
        reason = "missing-exact-object" if str(exc).startswith("missing exact dependency object") else "unknown-condition"
        return reason, None
    objects = frozenset(row["hash"] for row in resolved["index"]["objects"])
    if set(snapshot.requests) != objects or len(snapshot.requests) != len(objects):
        raise AssertionError("Exact traversal did not request each included object once")
    return "resolved", (objects, resolved["index"])


def pinned(snapshot, policy, profile, supplied):
    wanted = receipt(snapshot, policy, profile)
    if supplied != wanted:
        return "invalid-condition-receipt", None
    return resolve(snapshot, policy, supplied.decisions)


def reference(profile, policy, missing):
    active = {"app"}
    if policy == "roots_only":
        return "resolved", frozenset({HASH["app"]})

    active.add(profile.target)
    if profile.network:
        active.add("network")
    if policy == "closure_with_optional" and profile.logging:
        active.update(("logging", "linux", "tail", "network"))
    if "network" in active and profile.tls:
        active.update(("tls", "tail"))
    if missing in active:
        return "missing-exact-object", None
    return "resolved", frozenset(HASH[name] for name in active)


def without_index(observed):
    status, result = observed
    return status, result[0] if result else None


def tally():
    profiles = tuple(Profile(*combination) for combination in
                     product(("linux", "windows"), (True, False), (True, False), (True, False)))
    snapshots = [Snapshot(missing) for missing in (None, "linux", "tls", "logging", "tail")]
    counts = Counter()
    by_policy = {policy: Counter() for policy in POLICIES}
    for snapshot, policy, actual, stale in product(snapshots, POLICIES, profiles, profiles):
        missing = snapshot.snapshot_id.removeprefix("fixture-without-")
        expected = reference(actual, policy, missing)
        supplied = receipt(snapshot, policy, stale)
        weak = without_index(resolve(snapshot, policy, supplied.decisions))
        strict = without_index(pinned(snapshot, policy, actual, supplied))
        counts["queries"] += 1
        policy_counts = by_policy[policy]
        if weak != expected:
            counts["bare_incorrect"] += 1
            policy_counts["bare_incorrect"] += 1
            if weak[0] == expected[0] == "resolved":
                policy_counts["wrong_membership"] += 1
            elif weak[0] == "resolved":
                policy_counts["missed_required_failure"] += 1
            else:
                policy_counts["incorrect_refusal"] += 1
        if actual == stale:
            if strict != expected:
                raise AssertionError((snapshot.snapshot_id, policy, actual, expected, strict))
            counts["exact_current_matches"] += 1
            counts[f"current_{strict[0]}"] += 1
        else:
            if strict != ("invalid-condition-receipt", None):
                raise AssertionError("Stale context receipt became admissible")
            counts["exact_stale_refusals"] += 1

    snapshot = snapshots[0]
    profile = Profile("linux", False, False, False)
    baseline = receipt(snapshot, "closure", profile)
    status, result = pinned(snapshot, "closure", profile, baseline)
    assert status == "resolved"
    by_id = {record["edge_id"]: record for record in result[1]["dependencies"]}
    assert by_id["optional-linux-alias"]["included"]
    assert not by_id["reported-target"]["included"]
    assert {key[1]: active for key, active in baseline.decisions}["optional-linux-alias"] is False
    omitted = tuple((key, val) for key, val in baseline.decisions if key[1] != "choose-linux")
    flipped = tuple((key, not val if key[1] == "choose-linux" else val)
                    for key, val in baseline.decisions)
    report = {
        "baseline_members": sorted(result[0]),
        "inactive_optional_edge_can_have_included_target": by_id["optional-linux-alias"]["included"],
        "target_kind_does_not_trigger_enumeration": not by_id["reported-target"]["included"],
        "bare_missing_condition": resolve(snapshot, "closure", omitted)[0],
        "receipt_changed_decision": pinned(snapshot, "closure", profile, replace(baseline, decisions=flipped))[0],
        "receipt_missing_condition": pinned(snapshot, "closure", profile, replace(baseline, decisions=omitted))[0],
        "receipt_stale_snapshot": pinned(snapshots[1], "closure", profile, baseline)[0],
        "receipt_stale_policy": pinned(snapshot, "closure_with_optional", profile, baseline)[0],
        "receipt_wrong_root": pinned(snapshot, "closure", profile, replace(baseline, roots=(HASH["linux"],)))[0],
    }
    assert report["bare_missing_condition"] == "unknown-condition"
    assert all(report[name] == "invalid-condition-receipt" for name in
               ("receipt_missing_condition", "receipt_changed_decision", "receipt_stale_snapshot",
                "receipt_stale_policy", "receipt_wrong_root"))
    files = (HERE / "run.py", PROTOTYPE / "package_closure.py", PROTOTYPE / "package_index.py")
    return {
        "profiles": len(profiles),
        "availability_fixtures": len(snapshots),
        "counts": dict(sorted(counts.items())),
        "bare_errors_by_policy": {policy: dict(sorted(by_policy[policy].items())) for policy in POLICIES},
        "focused_controls": report,
        "source_sha256": {path.relative_to(HERE.parents[3]).as_posix(): sha256(path.read_bytes()).hexdigest()
                          for path in files},
    }


if __name__ == "__main__":
    print(json.dumps(tally(), indent=2))
