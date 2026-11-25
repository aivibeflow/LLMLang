"""Model exact semantic, dependency-lock and mapping merge subjects."""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import subprocess


BASE = "9cbe01391f984a62c7a6309b09bbd86cf60bf4ed"
RT24 = "research/toolchain-and-collaboration/RT-24"


def digest(payload):
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def identities(tree, selection, tool, policy):
    git_record = digest(["git-provenance", tree])
    semantic = digest(["semantic-selection", selection])
    action = digest(["action", semantic, tool])
    proof = digest(["evidence", semantic, action, policy])
    return {"git": git_record, "semantic": semantic, "action": action, "evidence": proof}


def scope_controls():
    base = identities("tree1", "graph1", "tools1", "policy1")
    controlled = {
        "physical-tree": (identities("tree2", "graph1", "tools1", "policy1"), {"git"}),
        "semantic-selection": (identities("tree1", "graph2", "tools1", "policy1"), {"semantic", "action", "evidence"}),
        "toolchain": (identities("tree1", "graph1", "tools2", "policy1"), {"action", "evidence"}),
        "evidence-policy": (identities("tree1", "graph1", "tools1", "policy2"), {"evidence"}),
    }
    for alternative, changed in controlled.values():
        assert {name for name in base if base[name] != alternative[name]} == changed
    return {scenario: sorted(changed) for scenario, (_, changed) in controlled.items()}


def combine(base, ours, theirs, plane):
    result = {}
    conflicts = []
    for name in sorted(base.keys() | ours.keys() | theirs.keys()):
        before, left, right = base.get(name), ours.get(name), theirs.get(name)
        if left == before:
            chosen = right
        elif right == before:
            chosen = left
        elif left == right and plane not in {"mapping", "lineage"} and before is not None:
            chosen = left
        else:
            conflicts.append(name)
            continue
        if chosen is not None:
            result[name] = chosen
    return result, conflicts


def gate(base, ours, theirs, expected_revision, actual_revision):
    if expected_revision != actual_revision:
        return "insufficient-context", None
    merged = {}
    conflicts = []
    for plane in base:
        result, blocked = combine(base[plane], ours[plane], theirs[plane], plane)
        merged[plane] = result
        conflicts.extend((plane, key) for key in blocked)
    if conflicts:
        return "conflict", tuple(conflicts)
    if any(merged["locks"].get(key) != version for key, version in merged["depends"].items()):
        return "invalid", "dependency-lock"
    if any(slot not in merged["entities"] for slot in merged["mapping"].values()):
        return "invalid", "mapping-target"
    return "clean-within-profile", merged


def changed(base, **overrides):
    return {**base, **overrides}


def cases():
    base = {
        "entities": {"entry": "lifetime-a/body-v1", "helper": "lifetime-b/body-v1"},
        "locks": {"pkg": "v1"}, "depends": {"pkg": "v1"},
        "mapping": {"entry": "entry", "helper": "helper"}, "lineage": {},
    }
    a, b = base["entities"].values()
    split = changed(base, entities={"entry-a": "fresh-c", "entry-b": "fresh-d", "helper": b},
                    mapping={"entry": "entry-a", "helper": "helper"},
                    lineage={"lifetime-a": "split:c,d"})
    merge = changed(base, entities={"merged": "fresh-e"}, mapping={"entry": "merged", "helper": "merged"},
                    lineage={"lifetime-a": "merge:e", "lifetime-b": "merge:e"})
    cases = {
        "independent-add-add": (changed(base, entities={**base["entities"], "c": "fresh-c"}),
                                changed(base, entities={**base["entities"], "d": "fresh-d"}), "clean-within-profile"),
        "equal-payload-independent-add": (changed(base, entities={**base["entities"], "c": "fresh-c"}),
                                         changed(base, entities={**base["entities"], "c": "fresh-c"}), "conflict"),
        "same-occurrence-diverges": (changed(base, entities={"entry": "lifetime-a/body-v2", "helper": b}),
                                     changed(base, entities={"entry": "lifetime-a/body-v3", "helper": b}), "conflict"),
        "delete-update": (changed(base, entities={"helper": b}, mapping={"helper": "helper"}),
                          changed(base, entities={"entry": "lifetime-a/body-v2", "helper": b}), "conflict"),
        "move-and-independent-update": (changed(base, entities={"moved": a, "helper": b},
                                               mapping={"entry": "moved", "helper": "helper"}),
                                        changed(base, entities={"entry": a, "helper": "lifetime-b/body-v2"}),
                                        "clean-within-profile"),
        "split": (split, base, "clean-within-profile"),
        "merge": (base, merge, "clean-within-profile"),
        "split-merge": (split, merge, "conflict"),
        "replacement": (changed(base, entities={"entry": "fresh-f/body-v1", "helper": b},
                                 lineage={"lifetime-a": "replaced-by:f"}), base, "clean-within-profile"),
        "mapping-both-edits": (changed(base, mapping={"entry": "helper", "helper": "helper"}),
                               changed(base, mapping={"entry": "helper", "helper": "helper"}), "conflict"),
        "lock-change-with-unmigrated-caller": (changed(base, locks={"pkg": "v2"}), base, "invalid"),
        "lock-and-caller-aligned": (changed(base, locks={"pkg": "v2"}),
                                   changed(base, depends={"pkg": "v2"}), "clean-within-profile"),
    }
    output = {}
    for name, (left, right, expected) in cases.items():
        first = gate(base, left, right, "r2", "r2")
        assert first == gate(base, right, left, "r2", "r2")
        assert first[0] == expected, (name, first)
        contexts = identities(["parents", name], first, "tooling-v1", "required-scope")
        assert len(set(contexts.values())) == 4
        output[name] = {"verdict": first[0], "record_digests": contexts}
    assert gate(base, base, base, "r1", "r2") == ("insufficient-context", None)
    return {"cases": output, "totals": dict(Counter(row["verdict"] for row in output.values())),
            "stale_mapping_baseline": "insufficient-context"}


def archive():
    inputs = ("PURE-MERGE-CORE-01", "IDENTITY-LINEAGE-01", "CROSS-MAP-REFS-01", "CONFLICT-RESOLUTION-01")
    return {fixture: sha256(subprocess.check_output(
        ["git", "show", f"{BASE}:{RT24}/{fixture}/evidence.json"],
    )).hexdigest() for fixture in inputs}


if __name__ == "__main__":
    print(json.dumps({
        "baseline": BASE, "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "prior_ledgers": archive(), "comparison": cases(), "identity_edits": scope_controls(),
    }, sort_keys=True, indent=2))
