"""Compare replay of an equal merge result with replay of its validation audit."""

from copy import deepcopy
import hashlib
import json
import platform


def hash_value(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def merge(base, left, right):
    candidate = {}
    for slot, original in sorted(base.items()):
        ours, theirs = left[slot], right[slot]
        if ours != theirs and ours != original and theirs != original:
            raise ValueError(f"unresolved slot: {slot}")
        candidate[slot] = theirs if ours == original else ours
    return candidate


def evaluate(inputs, candidate, profile):
    request = {
        "parents": [hash_value(parent) for parent in inputs],
        "candidate": hash_value(candidate),
        "profile": hash_value(profile),
    }
    checks = {
        "closure": ("pass", "references-resolve")
        if candidate["consumer"]["target"] in candidate else ("fail", "unresolved-target"),
        "capacity": ("pass", "within-capacity")
        if candidate["provider"]["capacity"] >= candidate["consumer"]["quantity"]
        else ("fail", "insufficient-capacity"),
        "budget": ("pass", "within-budget")
        if candidate["provider"]["cost"] <= profile["budget"] else ("fail", "budget-exceeded"),
    }
    unknown = set(profile["required"]) - checks.keys()
    assert not unknown
    receipts = [
        {"rule": rule, "status": checks[rule][0], "reason": checks[rule][1], "request": hash_value(request)}
        for rule in sorted(profile["required"])
    ]
    decision = "publishable" if all(row["status"] == "pass" for row in receipts) else "blocked"
    return {"request": request, "receipts": receipts, "decision": decision}


def compare(candidate, supplied, fresh):
    result_matches = supplied["request"]["candidate"] == hash_value(candidate)
    supplied_rows = sorted(supplied["receipts"], key=lambda row: row["rule"])
    audit_matches = (
        supplied["request"] == fresh["request"]
        and supplied_rows == fresh["receipts"]
        and supplied["decision"] == fresh["decision"]
    )
    return {
        "result_matches": result_matches,
        "audit_matches": audit_matches,
        "decision_after_verified_replay": fresh["decision"] if audit_matches else "unverified",
    }


def study():
    base = {
        "provider": {"capacity": 6, "cost": 5},
        "consumer": {"target": "provider", "quantity": 4},
    }
    left = base | {"provider": {"capacity": 8, "cost": 7}}
    right = base | {"consumer": {"target": "provider", "quantity": 6}}
    inputs = (base, left, right)
    candidate = merge(*inputs)
    profile = {"version": 1, "budget": 8, "required": ["budget", "capacity", "closure"]}
    lower_budget = profile | {"budget": 6}
    baseline = evaluate(inputs, candidate, profile)
    equivalent = evaluate(inputs, candidate, profile | {"version": 2})
    blocked = evaluate(inputs, candidate, lower_budget)
    swapped_inputs = (base, right, left)
    assert merge(*swapped_inputs) == candidate
    swapped = evaluate(swapped_inputs, candidate, profile)

    reversed_rows = baseline | {"receipts": list(reversed(baseline["receipts"]))}
    removed = blocked | {"receipts": blocked["receipts"][1:], "decision": "publishable"}
    duplicate = baseline | {"receipts": baseline["receipts"] + baseline["receipts"][:1]}
    false_reason = deepcopy(baseline)
    false_reason["receipts"][0]["reason"] = "waived"
    mixed = blocked | {"receipts": baseline["receipts"][:1] + blocked["receipts"][1:]}
    contradicted = blocked | {"decision": "publishable"}
    cases = {
        "exact_acceptance": (baseline, baseline, "publishable"),
        "permuted_receipts": (reversed_rows, baseline, "publishable"),
        "exact_rejection": (blocked, blocked, "blocked"),
        "equal_outcomes_changed_policy_revision": (baseline, equivalent, "unverified"),
        "changed_budget_same_candidate": (baseline, blocked, "unverified"),
        "exchanged_ordered_inputs": (baseline, swapped, "unverified"),
        "omitted_failure": (removed, blocked, "unverified"),
        "duplicated_receipt": (duplicate, baseline, "unverified"),
        "changed_reason": (false_reason, baseline, "unverified"),
        "mixed_revision_receipts": (mixed, blocked, "unverified"),
        "decision_conflicts_with_receipts": (contradicted, blocked, "unverified"),
    }
    results = {}
    for name, (supplied, current, expected) in cases.items():
        observed = compare(candidate, supplied, current)
        assert observed == {
            "result_matches": True,
            "audit_matches": expected != "unverified",
            "decision_after_verified_replay": expected,
        }
        results[name] = {"supplied": supplied, "fresh": current, "comparison": observed}
    return {
        "runtime": platform.python_version(),
        "inputs": inputs,
        "candidate": candidate,
        "profiles": [profile, profile | {"version": 2}, lower_budget],
        "cases": results,
    }


if __name__ == "__main__":
    print(json.dumps(study(), indent=2, sort_keys=True))
