"""Reconcile archived conflict, fallback, closure and review results."""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PINS = {
    "CONSERVATIVE-MERGE-01": "ee1c4a82475a1159e22eabceb44af23fe2231418fb6e30dff5a40c19104fa42d",
    "MERGE-FALLBACK-01": "29e779da320e7d535ed8084aaf83223ab01d61d290a6248b25d8593ebd96aa50",
    "MERGE-COVERAGE-01": "16c74fc42ba604fea6c1649e3d1adf60e67875781116589d12f8d1f4cd900cf8",
    "CONFLICT-RESOLUTION-01": "8b06849b3089d119276382c4100a022441f1fc2f85a47b12add7015998c45872",
}


def read(name):
    data = (HERE.parent / name / "evidence.json").read_bytes()
    assert sha256(data).hexdigest() == PINS[name]
    return json.loads(data)


def check():
    verification = read("CONSERVATIVE-MERGE-01")["cases"]
    temporary = Counter(row["after_fresh_check"]["decision"] for row in verification.values()
                        if row["initial"]["decision"] == "pending")
    assert temporary == {"eligible": 4, "conflict": 3}
    fallback = read("MERGE-FALLBACK-01")["cases"]
    clean = [row for row in fallback if row["git_exit"] == 0]
    assert len(clean) == 3 and sum(row["candidate_eligible"] for row in clean) == 1
    remain = [row for row in fallback if row["git_exit"] != 0]
    assert len(remain) == 3 and all(set(row["stages"]) == {1, 2, 3} for row in remain)
    coverage = read("MERGE-COVERAGE-01")["cases"]
    structural = sum(row["structural_candidate"] for row in coverage)
    eligible = sum(row["gate"] == "clean-within-profile" for row in coverage)
    assert (len(coverage), structural, eligible) == (165, 110, 1)
    scopes = read("CONFLICT-RESOLUTION-01")["cases"]
    blocked = sorted(name for name, row in scopes.items()
                     if row["admitted"]["slot_only"] and not row["admitted"]["scoped_exact_incoming"])
    assert blocked == ["affected_guard_change", "dependent_and_removed_retention", "new_affected_caller"]
    return {"sources": PINS, "pending_rechecks": temporary,
            "git_clean_candidates": len(clean), "git_clean_ineligible": len(clean) - 1,
            "unmerged_original_stage_sets": len(remain),
            "structural_candidates": structural, "profile_eligible": eligible,
            "stale_local_review_refusals": blocked,
            "checker_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(check(), sort_keys=True, indent=2))
