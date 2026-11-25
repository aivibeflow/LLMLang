"""Check exact task completion obligations and reproducible scoped receipts."""

from collections import Counter
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import permutations, product
import json
from pathlib import Path
import platform


ISSUERS = {
    "required-mutation": "toolchain",
    "tests": "test-runner",
    "proof": "proof-checker",
    "audit": "independent-auditor",
    "approval": "authorized-reviewer",
}


@dataclass(frozen=True)
class Subject:
    task: str
    revision: int
    baseline: str
    manifest: str
    candidate: str
    policy: str


@dataclass(frozen=True)
class Evidence:
    role: str
    issuer: str
    scope: Subject
    verdict: str


CURRENT = Subject("fixture-task", 2, "old-root", "exact-context-manifest", "prepared-candidate", "policy:4")


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def completion(scope, live_baseline, observations):
    if scope.baseline != live_baseline:
        return "stale-baseline", None
    by_role = {}
    for record in observations:
        if record.role not in ISSUERS or record.issuer != ISSUERS[record.role] or record.scope != scope:
            continue
        by_role.setdefault(record.role, set()).add(record)
    if set(by_role) != set(ISSUERS):
        return "incomplete", None
    if any(len(records) != 1 or next(iter(records)).verdict != "pass" for records in by_role.values()):
        return "unsatisfied", None
    facts = {role: digest(asdict(next(iter(records)))) for role, records in by_role.items()}
    return "complete", digest({"scope": asdict(scope), "evidence": facts})


def run():
    controls = {}
    exact = [Evidence(role, issuer, CURRENT, "pass") for role, issuer in ISSUERS.items()]
    known = completion(CURRENT, CURRENT.baseline, exact)
    assert known[0] == "complete"
    outcomes = Counter()
    for states in product(("exact", "missing", "unknown", "failed"), repeat=5):
        evidence = [record if state == "exact" else replace(record, verdict=state)
                    for record, state in zip(exact, states, strict=True) if state != "missing"]
        result, receipt = completion(CURRENT, CURRENT.baseline, evidence)
        expected = "incomplete" if "missing" in states else (
            "unsatisfied" if "unknown" in states or "failed" in states else "complete")
        assert result == expected
        assert (receipt is not None) == (expected == "complete")
        outcomes[result] += 1
    for order in permutations(exact):
        assert completion(CURRENT, CURRENT.baseline, order) == known

    controls["stale_baseline"] = completion(CURRENT, "later", exact)[0]
    controls["different_manifest"] = completion(replace(CURRENT, manifest="other"), CURRENT.baseline, exact)[0]
    controls["wrong_audit_issuer"] = completion(CURRENT, CURRENT.baseline, [
        replace(row, issuer="toolchain") if row.role == "audit" else row for row in exact
    ])[0]
    controls["conflicting_approval"] = completion(CURRENT, CURRENT.baseline, [
        *exact, replace(exact[-1], verdict="fail")
    ])[0]
    controls["duplicate_exact_approval"] = completion(CURRENT, CURRENT.baseline, [*exact, exact[-1]])[0]
    assert controls == {"stale_baseline": "stale-baseline", "different_manifest": "incomplete",
                        "wrong_audit_issuer": "incomplete", "conflicting_approval": "unsatisfied",
                        "duplicate_exact_approval": "complete"}
    return {"python": platform.python_version(), "checks": sum(outcomes.values()), "outcomes": outcomes,
            "permutations": 120, "exact_completed_receipt": known[1], "required_issuers": ISSUERS,
            "controls": controls, "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
