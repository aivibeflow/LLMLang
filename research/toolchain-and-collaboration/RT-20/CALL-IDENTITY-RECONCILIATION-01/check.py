"""Check archived caller identity, propagation and continuity outcomes."""

from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PINS = {
    "RT-24/IDENTITY-LINEAGE-01": "5c0126baa4d2a8668ef5b49f93984c5403d7f64711fb3367654618f1020f5f1d",
    "RT-20/NATIVE-PROPAGATION-01": "1e4ccdc732ed3a0dec548ff2ad02a05b7737155d70d2f4c66d00a74ae6f648fc",
    "RT-20/FORK-IDENTITY-01": "a9750b62ff445c259b4d4a7887ef60a2c8e967b9b1e805be1b0ae6bbdef52a6e",
}


def load(name):
    raw = (HERE.parents[1] / name / "evidence.json").read_bytes()
    assert sha256(raw).hexdigest() == PINS[name]
    return json.loads(raw)


def check():
    lineage, native, fork = [load(name) for name in PINS]
    assert lineage["total"] == 704
    assert lineage["equal_content_different_stable_id"] == "invalid-lineage"
    assert lineage["single_caller_receipt_in_split"] == "missing-rebind-evidence"
    kept = set(native["unchanged_baseline_hashes"])
    rebound = set(native["rebound_existing_hashes"])
    assert len(kept) == len(rebound) == 5 and not kept & rebound
    assert native["native_invocations"] == 2376
    assert (fork["ordered_replays"], fork["base_key_cardinality"], fork["path_key_cardinality"]) == (288, 2, 6)
    assert len({row["id"] for row in fork["exact_decision_ids"]}) == 6
    assert "independent completeness is required" in fork["omitted_decision_control"]
    return {"receipts": PINS, "native_invocations": native["native_invocations"],
            "preserved_roles": sorted(kept), "rebound_roles": sorted(rebound),
            "path_decisions": fork["path_key_cardinality"],
            "lineage_profiles": lineage["total"],
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(check(), sort_keys=True, indent=2))
