"""Reconcile typed merge observations and check a scoped conflict projection."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess


BASE = "aeebb503a2852833632b82f31bc393d1c0652a3b"
RT24 = "research/toolchain-and-collaboration/RT-24"
CLASSES = {
    "divergent-selection": "same-node",
    "unsatisfied-selected-contract": "contract-implementation",
    "nonunique-new-lifetime": "identity-collision",
    "missing-required-target": "dependency",
    "incompatible-resolution-edges": "split-merge",
    "divergent-review-note": "metadata",
}


def candidate_disposition(findings, complete):
    known = frozenset(CLASSES[finding] for finding in findings)
    if known - {"metadata"}:
        return "semantic-conflict", sorted(known)
    if not complete:
        return "insufficient-context", sorted(known)
    return ("metadata-conflict" if known else "structural-candidate"), sorted(known)


def check_dispositions():
    taxonomy = Counter()
    all_findings = tuple(CLASSES)
    for checks in product((False, True), repeat=7):
        flags, complete = checks[:-1], checks[-1]
        checks_by_name = dict(zip(all_findings, flags, strict=True))
        findings = [name for name in all_findings if checks_by_name[name]]
        status, conflicts = candidate_disposition(findings, complete)
        if any(flags[:-1]):
            assert status == "semantic-conflict"
        elif complete:
            assert status == ("metadata-conflict" if flags[-1] else "structural-candidate")
        else:
            assert status == "insufficient-context"
        assert len(conflicts) == sum(flags)
        assert candidate_disposition(reversed(findings), complete) == (status, conflicts)
        taxonomy[status] += 1
    return dict(taxonomy)


def read(study):
    path = f"{RT24}/{study}/evidence.json"
    raw = subprocess.check_output(["git", "show", f"{BASE}:{path}"])
    return json.loads(raw), {path: sha256(raw).hexdigest()}


def archives():
    core, core_sha = read("PURE-MERGE-CORE-01")
    views, views_sha = read("DIFF-OBSERVATION-LAYERS-01")
    dual, dual_sha = read("CONTRACT-BODY-MERGES-01")
    lineage, lineage_sha = read("IDENTITY-LINEAGE-01")
    counts = core["exhaustive"]["two_slot_results"]
    assert counts == {"conflicted": 2727, "resolved": 1369}
    assert dual["native_merges"] == 32 and dual["combined_refused"] == 7
    assert len(views["cases"]) == 8 and lineage["total"] == 704
    return {"digests": {**core_sha, **views_sha, **dual_sha, **lineage_sha},
            "core_cases": counts, "diff_cases": len(views["cases"]),
            "native_contract_merge_refusals": dual["combined_refused"], "lineage_cases": lineage["total"]}


if __name__ == "__main__":
    print(json.dumps({
        "baseline": BASE, "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "archive": archives(), "classification_cases": check_dispositions(),
    }, sort_keys=True, indent=2))
