"""Check conservative handling of incomplete merge evidence in a finite model."""

import hashlib
import itertools
import json
import platform
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "MERGE-AUDIT-REPLAY-01"))
from run import hash_value

BASELINE = "9fc1bde0127bd55aea65b58752d5af8c38390bf9"
STATES = tuple(itertools.product((0, 1), repeat=2))
BASE = (0, 0)
SET_A = {"write": 0, "constant": 1}
SET_B = {"write": 1, "constant": 1}
RESET_A = {"write": 0, "constant": 0}
COPY_A_TO_B = {"write": 1, "read": 0}


def apply(edit, state):
    next_state = list(state)
    next_state[edit["write"]] = state[edit["read"]] if "read" in edit else edit["constant"]
    return tuple(next_state)


def request(ours, theirs, capacity):
    return {"schema": "finite-merge/v1", "base": BASE, "ordered_alternatives": [ours, theirs],
            "domain": STATES, "capacity": capacity}


def observation(query, limit):
    ours, theirs = query["ordered_alternatives"]
    checked = []
    for case in query["domain"][:limit]:
        first = apply(theirs, apply(ours, case))
        second = apply(ours, apply(theirs, case))
        checked.append({"state": case, "ours_then_theirs": first, "theirs_then_ours": second})
        if first != second:
            break
    if checked and first != second:
        status = "noncommuting"
    elif len(checked) == len(query["domain"]):
        status = "commutes"
    else:
        status = "unknown"
    return {"subject": hash_value(query), "status": status, "evaluation_limit": limit,
            "checked": checked}


def route(query, receipt):
    retained = {"request": query, "receipt": receipt, "candidate": None}
    if receipt is None:
        return retained | {"decision": "pending", "reason": "check-missing"}
    if receipt["subject"] != hash_value(query):
        return retained | {"decision": "pending", "reason": "check-stale"}
    if receipt["status"] == "unknown":
        return retained | {"decision": "pending", "reason": "check-incomplete"}
    if receipt["status"] == "noncommuting":
        return retained | {"decision": "conflict", "reason": "order-dependent"}
    assert receipt["status"] == "commutes"
    ours, theirs = query["ordered_alternatives"]
    candidate = apply(theirs, apply(ours, query["base"]))
    if sum(candidate) > query["capacity"]:
        return retained | {"decision": "conflict", "reason": "capacity", "rejected_state": candidate}
    return retained | {"decision": "eligible", "reason": "complete-and-valid", "candidate": candidate}


def main():
    passing = request(SET_A, SET_B, 2)
    failing = request(RESET_A, COPY_A_TO_B, 2)
    tight = request(SET_A, SET_B, 1)
    reordered = request(SET_B, SET_A, 2)
    proved = observation(passing, 4)
    limited = observation(passing, 1)
    limited_failure = observation(failing, 1)
    witness = observation(failing, 4)
    assert observation(failing, 2)["status"] == "unknown"
    assert witness["checked"][-1] == {
        "state": (1, 0), "ours_then_theirs": (0, 0), "theirs_then_ours": (0, 1),
    }
    assert all(sum(apply(edit, BASE)) <= tight["capacity"] for edit in (SET_A, SET_B))
    assert hash_value(reordered) != proved["subject"]
    cases = {
        "absent": (passing, None, ("pending", "check-missing")),
        "no-checks-run": (passing, observation(passing, 0), ("pending", "check-incomplete")),
        "truncated-valid": (passing, limited, ("pending", "check-incomplete")),
        "truncated-invalid": (failing, limited_failure, ("pending", "check-incomplete")),
        "completed-valid": (passing, proved, ("eligible", "complete-and-valid")),
        "completed-invalid": (failing, witness, ("conflict", "order-dependent")),
        "changed-alternative": (failing, proved, ("pending", "check-stale")),
        "reordered-alternatives": (reordered, proved, ("pending", "check-stale")),
        "changed-capacity": (tight, proved, ("pending", "check-stale")),
        "completed-postcheck-failure": (tight, observation(tight, 4), ("conflict", "capacity")),
        "recomputed-reordered": (reordered, observation(reordered, 4), ("eligible", "complete-and-valid")),
    }
    rows = {}
    for name, (query, receipt, expected) in cases.items():
        result = route(query, receipt)
        assert (result["decision"], result["reason"]) == expected
        assert result["request"]["ordered_alternatives"] == query["ordered_alternatives"]
        assert result["candidate"] == ((1, 1) if expected[0] == "eligible" else None)
        terminal = route(query, observation(query, 4))
        recovered = json.loads(json.dumps(result))["request"]
        assert hash_value(recovered) == hash_value(query)
        assert hash_value(route(recovered, observation(recovered, 4))) == hash_value(terminal)
        rows[name] = {"initial": result, "after_fresh_check": terminal}
    assert rows["truncated-valid"]["after_fresh_check"]["decision"] == "eligible"
    assert rows["truncated-invalid"]["after_fresh_check"]["decision"] == "conflict"
    helper = HERE.parent / "MERGE-AUDIT-REPLAY-01" / "run.py"

    relative = str(helper.relative_to(HERE.parents[3]))
    archived = subprocess.check_output(["git", "show", f"{BASELINE}:{relative}"], cwd=HERE.parents[3])
    assert archived == helper.read_bytes()
    print(json.dumps({
        "baseline": BASELINE, "python": platform.python_version(),
        "git": subprocess.check_output(["git", "--version"], text=True).strip(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "helper_sha256": hashlib.sha256(archived).hexdigest(), "cases": rows,
    }, indent=2))


if __name__ == "__main__":
    main()
