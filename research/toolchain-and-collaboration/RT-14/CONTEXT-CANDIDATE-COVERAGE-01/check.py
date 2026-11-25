"""Verify the supporting ledgers for context deployment and task ownership alternatives."""

from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PINS = {
    "TASK-SIBLINGS-01": "81823ddf0ad234e2a98e120422f8da3b6e72c00e99454e9a093a74027668a6a9",
    "TASK-CONTEXT-SQLITE-01": "aa5a20b4c8c73f9194b638ef5539e7e435ef82cb428b66c28fe038bb9ce85986",
    "TASK-AUTHORITY-01": "5789127344ea3e40973c9d0f51da57c3601921d68c4bc406d9ddc7048d4cca6d",
}


def load(name):
    raw = (HERE.parent / name / "evidence.json").read_bytes()
    assert sha256(raw).hexdigest() == PINS[name]
    return json.loads(raw)


def check():
    siblings, settlement, authority = [load(name) for name in PINS]
    assert siblings["overlapping_delegate_race"][0] == ["delegated", "overlap"]
    assert siblings["disjoint_delegate_race"][0] == ["delegated", "delegated"]
    assert siblings["cancel_before_settle"] == ["inactive", 0]
    assert siblings["settle_before_cancel"] == ["settled", 1]
    assert siblings["settled_siblings_without_full_scope"] == "pending-scope"
    wrong = settlement["invalid_completions"]
    assert wrong == {"stationary-task": 6, "task-cas": 3, "exact-prerequisites": 0}
    retry = settlement["transaction_retry"]
    assert retry["fresh_retry"] == "completed" and retry["repeat_after_fresh_open"] == "recorded"
    assert retry["same_key_other_request"] == "request-id-conflict" and len(retry["final_receipts"]) == 1
    assert authority["admission_checks"] == 120 and authority["authorized_in_matrix"] == 2
    assert authority["commit_approval_cannot_authorize_push"] == "approval-binding-mismatch"
    return {"source_ledgers": PINS, "wrong_completions": wrong, "retry_terminal_receipts": len(retry["final_receipts"]),
            "action_grant_cases": authority["admission_checks"], "action_grant_passes": 2,
            "native_delegation_races": 2 * siblings["concurrent_repetitions_per_scope_case"],
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(check(), sort_keys=True, indent=2))
