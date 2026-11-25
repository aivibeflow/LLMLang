"""Compare review-subject identities for one typed semantic change."""

from collections import deque
import hashlib
import json
from pathlib import Path
import platform

BASELINE = "b076f3abbb798f7c9753236a366aea595654f535"
FOCUS = "binding:compute"


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def node(kind, payload, *dependencies):
    return {"kind": kind, "payload": payload, "dependencies": sorted(dependencies)}


def validate(graph):
    for slot, row in graph.items():
        if set(row["dependencies"]) - graph.keys():
            raise ValueError(f"unresolved dependency at {slot}")
        if len(row["dependencies"]) != len(set(row["dependencies"])):
            raise ValueError(f"repeated dependency at {slot}")


def reachable(edges, start):
    discovered = set(start)
    queue = deque(sorted(discovered))
    while queue:
        for target in edges[queue.popleft()]:
            if target not in discovered:
                discovered.add(target)
                queue.append(target)
    return discovered


def project(graph, focus):
    forward = {slot: row["dependencies"] for slot, row in graph.items()}
    reverse = {slot: [] for slot in graph}
    for slot, dependencies in forward.items():
        for target in dependencies:
            reverse[target].append(slot)
    affected = reachable(reverse, (focus,))
    return affected, reachable(forward, affected)


def subject(before, after, focus, policy):
    validate(before)
    validate(after)
    old_affected, old_scope = project(before, focus)
    new_affected, new_scope = project(after, focus)
    rows = {
        slot: {"before": before.get(slot), "after": after.get(slot)}
        for slot in sorted(old_scope | new_scope)
    }
    change = {"focus": focus, "before": before[focus], "after": after[focus], "policy": policy}
    capsule = change | {"rows": rows, "affected": [sorted(old_affected), sorted(new_affected)]}
    keys = {
        "label": digest(focus),
        "direct": digest(change),
        "closed": digest(capsule),
        "complete": digest({"ordered_roots": [digest(before), digest(after)],
                            "focus": focus, "policy": policy}),
    }
    return {"capsule": capsule, "keys": keys}


def exercise():
    before = {
        FOCUS: node("binding", "select plus", "impl:plus"),
        "impl:plus": node("implementation", "add one", "abi"),
        "impl:minus": node("implementation", "subtract one", "abi"),
        "abi": node("runtime", "word32"),
        "client": node("operation", "call compute", FOCUS),
        "entry": node("operation", "call client", "client"),
        "manual": node("documentation", "revision 1"),
    }
    after = before | {FOCUS: node("binding", "select minus", "impl:minus")}
    approved = subject(before, after, FOCUS, "review/v1")
    assert set(approved["capsule"]["rows"]) == {
        FOCUS, "impl:plus", "impl:minus", "abi", "client", "entry",
    }
    all_gates = {"label", "direct", "closed", "complete"}
    extra = {"extra": node("operation", "call entry", "entry")}
    changed_docs = {"manual": node("documentation", "revision 2")}
    updated_provider = {"impl:minus": node("implementation", "subtract two", "abi")}
    changed_abi = {"abi": node("runtime", "word64")}
    without_entry = {slot: row for slot, row in after.items() if slot != "entry"}
    cases = {
        "exact": (before, after, "review/v1", all_gates),
        "different_key_order": (dict(reversed(before.items())), dict(reversed(after.items())),
                                "review/v1", all_gates),
        "unrelated_base": (before | changed_docs, after, "review/v1", all_gates - {"complete"}),
        "unrelated_candidate": (before, after | changed_docs, "review/v1", all_gates - {"complete"}),
        "new_transitive_consumer": (before, after | extra, "review/v1", {"label", "direct"}),
        "consumer_removed": (before, without_entry, "review/v1", {"label", "direct"}),
        "provider_body_changed": (before, after | updated_provider, "review/v1", {"label", "direct"}),
        "dependency_changed": (before, after | changed_abi, "review/v1", {"label", "direct"}),
        "reversed_roles": (after, before, "review/v1", {"label"}),
        "policy_changed": (before, after, "review/v2", {"label"}),
    }
    results = {}
    for name, (base, candidate, policy, expected) in cases.items():
        current = subject(base, candidate, FOCUS, policy)
        admitted = {gate for gate, key in current["keys"].items() if key == approved["keys"][gate]}
        assert admitted == expected, name
        results[name] = {"base": base, "candidate": candidate, "policy": policy,
                         "result": current, "approval_matches": sorted(admitted)}
    capsule = results["new_transitive_consumer"]["result"]["capsule"]
    assert capsule["rows"]["extra"]["before"] is None
    assert capsule["rows"]["extra"]["after"] == extra["extra"]
    assert capsule["affected"][1] == [FOCUS, "client", "entry", "extra"]
    invalid = {slot: row for slot, row in after.items() if slot != "impl:minus"}
    try:
        subject(before, invalid, FOCUS, "review/v1")
    except ValueError as error:
        results["incomplete_input"] = {"candidate": invalid, "refusal": str(error),
                                       "approval_matches": []}
    else:
        raise AssertionError("incomplete graph projected as valid")

    return {
        "baseline": BASELINE, "python": platform.python_version(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "focus": FOCUS, "original_review_subject": approved, "cases": results,
    }


if __name__ == "__main__":
    print(json.dumps(exercise(), indent=2))
