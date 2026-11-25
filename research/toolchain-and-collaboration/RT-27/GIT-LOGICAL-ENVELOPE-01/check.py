"""Reconcile native archive evidence for a canonical logical Git envelope."""

from collections import Counter
from hashlib import sha256
from itertools import permutations, product
import json
from pathlib import Path
import subprocess


BASE = "3fc3ce60b041052470abdb3376f7ad53bc25b113"
ROOT = "research/toolchain-and-collaboration"


def archive(topic, fixture):
    path = f"{ROOT}/{topic}/{fixture}/evidence.json"
    raw = subprocess.check_output(["git", "show", f"{BASE}:{path}"])
    return json.loads(raw), {path: sha256(raw).hexdigest()}


def verified_archives():
    closed, closed_hash = archive("RT-27", "GIT-CLOSED-REPRESENTATION-01")
    records, records_hash = archive("RT-27", "SPG-PROFILED-RECORDS-01")
    review, review_hash = archive("RT-27", "SPG-REVIEW-PROJECTION-01")
    merge, merge_hash = archive("RT-27", "TEXT-MERGE-GATE-01")
    commit, commit_hash = archive("RT-24", "COMMIT-TREE-SEMANTIC-ROOT-01")
    availability = Counter(row["available"] for row in closed["recovered"])
    assert sum(availability.values()) == 12 and availability["closed-offline"] == 8
    assert len(closed["refusals"]) == 10
    assert len(records["revisions"]) == 2 and records["fixed_buckets"] == 4
    assert len(review["rows"]) == 5 and review["repacked_review_changes"] == 0
    assert len(review["repacked_file_names"]) == 6
    merge_outcomes = Counter(row["semantic_gate"]["decision"] for row in merge["rows"])
    assert all(not row["git_conflicts"] for row in merge["rows"])
    assert merge_outcomes == {"validated": 8, "refused": 16}
    assert sum(len(value["rows"]) for value in commit["formats"].values()) == 16
    return {
        "pinned_sha256": {**closed_hash, **records_hash, **review_hash, **merge_hash, **commit_hash},
        "availability": dict(availability), "semantic_merge_controls": dict(merge_outcomes),
        "native_git_versions": sorted({closed["git"], commit["git"]}),
    }


def logical(snapshot, rows, reverse_profile, selection_profile):
    ids = {key for key, _ in rows}
    if len(ids) != len(rows) or snapshot not in ids:
        raise ValueError("ambiguous or missing exact object")
    data = ["logical-git-envelope/1", snapshot, sorted(rows), reverse_profile, selection_profile]
    return json.dumps(data, separators=(",", ":"), ensure_ascii=True).encode()


def envelope_checks():
    baseline = [("root", "sha256:root"), ("provider", "sha256:provider"), ("caller", "sha256:caller")]
    original = logical("root", baseline, "reverse-v1", "selected-v1")
    validated = 0
    distinct_transport = set()
    for order, placement, git_format in product(permutations(baseline), ("pack", "shard"), ("sha1", "sha256")):
        assert logical("root", order, "reverse-v1", "selected-v1") == original
        distinct_transport.add((placement, git_format))
        validated += 1
    changed = [*baseline[:-1], ("caller", "sha256:changed")]
    assert logical("root", changed, "reverse-v1", "selected-v1") != original
    for broken in (baseline[:-1] + [baseline[0]], baseline[1:]):
        try:
            logical("root", broken, "reverse-v1", "selected-v1")
        except ValueError:
            continue
        raise AssertionError("duplicate or missing root was admitted")
    return {"compared_logical_encodings": validated, "transport_labels": len(distinct_transport),
            "canonical_sha256": sha256(original).hexdigest()}


if __name__ == "__main__":
    print(json.dumps({
        "baseline": BASE, "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "archives": verified_archives(), "logical_envelope_checks": envelope_checks(),
    }, sort_keys=True, indent=2))
