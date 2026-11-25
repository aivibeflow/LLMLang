"""Assess deterministic clause reconstruction against an independent trace oracle."""

import hashlib
import json
import platform
import re
import subprocess
import sys
from itertools import product
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE = "e2e41096c5eeaba8bd35f7aa94e31eea02a45ca7"
LINE = re.compile(
    r"\[([a-z-]+)\] For (retail|wholesale|all) orders when reservation (succeeded|failed), "
    r"(require|forbid) (confirmation|notification) (.+)\."
)
WINDOW = re.compile(r"from (payment registration|reservation observation) through ([0-7]) seconds after it, inclusive")
HORIZON = 9
EVENT_TIMES = (None, *range(HORIZON + 1))
# Every trace has payment registration at second zero and reservation observation at second two.
TRACES = tuple(product(("retail", "wholesale"), ("succeeded", "failed"), EVENT_TIMES, EVENT_TIMES))


def semantic_payload(clauses):
    return [{key: value for key, value in clause.items() if key != "refs"} for clause in clauses]


def reconstruct(clauses):
    raw = subprocess.check_output(
        [sys.executable, "-B", str(HERE / "render.py")],
        input=json.dumps(semantic_payload(clauses)), text=True, timeout=10,
    )
    return json.loads(raw)


def decode(lines):
    clauses = {}
    for raw in lines:
        match = LINE.fullmatch(" ".join(raw.split()))
        if not match:
            return None
        identifier, scope, condition, mode, action, window = match.groups()
        timing = WINDOW.fullmatch(window)
        if identifier in clauses or (timing is None and window != "throughout the observed interval"):
            return None
        origin, deadline = timing.groups() if timing else (None, None)
        clauses[identifier] = {
            "id": identifier, "scope": scope, "condition": condition, "mode": mode,
            "action": action, "origin": origin, "deadline": int(deadline) if timing else None,
        }
    return clauses


def independently_expected(trace):
    """Manually adjudicated source meaning, independent of the typed clause evaluator."""
    scope, reservation, confirmed_at, _ = trace
    if scope == "wholesale":
        return True
    if reservation == "failed":
        return confirmed_at is None
    return confirmed_at in {0, 1, 2, 3, 4, 5}


def allows(clauses, trace):
    scope, condition, confirmation, notification = trace
    events = {"confirmation": confirmation, "notification": notification}
    for clause in clauses.values():
        if clause["scope"] not in {scope, "all"} or condition != clause["condition"]:
            continue
        start = 2 if clause["origin"] == "reservation observation" else 0
        end = HORIZON if clause["deadline"] is None else start + clause["deadline"]
        event = events[clause["action"]]
        happened = event is not None and start <= event <= end
        if happened != (clause["mode"] == "require"):
            return False
    return True


def source_problems(corpus, clauses):
    known = set(corpus["source_fragments"])
    authorized = set(corpus["authorized_fragments"])
    expected = {
        "deadline": ({"intent"}, {"operator"}, {"clock", "clock-copy"}),
        "exception": ({"operator"}, {"exception"}),
    }
    problems = {}
    for clause in clauses:
        key = clause["id"]
        references = set(clause["refs"])
        failures = []
        if references - known:
            failures.append("dangling")
        if (references & known) - authorized:
            failures.append("unapproved")
        role_groups = expected.get(key)
        if role_groups is None or any(not group & references for group in role_groups):
            failures.append("incomplete")
        if failures:
            problems[key] = failures
    return problems


def changed(clauses, identifier, **updates):
    return [{**clause, **updates} if clause["id"] == identifier else clause for clause in clauses]


def cases(clauses):
    deadline, exception = clauses
    extra = {**deadline, "id": "notification", "action": "notification", "refs": []}
    return (
        ("baseline", clauses, "ELIGIBLE", None),
        ("reordered", [exception, deadline], "ELIGIBLE", None),
        ("cosmetic-whitespace", clauses, "ELIGIBLE", "whitespace"),
        ("provenance-only", changed(clauses, "deadline", refs=["intent", "operator", "clock-copy"]), "ELIGIBLE", None),
        ("omitted-exception", [deadline], "DIFFERENT", None),
        ("added-notification", [*clauses, extra], "DIFFERENT", None),
        ("weaker-deadline", changed(clauses, "deadline", deadline=7), "DIFFERENT", None),
        ("stronger-deadline", changed(clauses, "deadline", deadline=3), "DIFFERENT", None),
        ("flipped-prohibition", changed(clauses, "exception", mode="require"), "DIFFERENT", None),
        ("shifted-clock", changed(clauses, "deadline", origin="reservation observation"), "DIFFERENT", None),
        ("expanded-scope", changed(clauses, "deadline", scope="all"), "DIFFERENT", None),
        ("shifted-trigger", changed(clauses, "deadline", condition="failed"), "DIFFERENT", None),
        ("missing-provenance", changed(clauses, "deadline", refs=["operator", "clock"]), "UNKNOWN", None),
        ("dangling-provenance", changed(clauses, "deadline", refs=["intent", "operator", "ghost"]), "UNKNOWN", None),
        ("conflicting-unapproved-provenance", changed(clauses, "deadline",
            refs=["intent", "operator", "clock", "conflicting-clock"]), "UNKNOWN", None),
        ("unsupported-action", changed(clauses, "deadline", action="email-or-webhook"), "UNKNOWN", None),
        ("unreadable-reconstruction", clauses, "UNKNOWN", "malformed"),
        ("unfaithful-reconstruction", clauses, "DIFFERENT", "altered-text"),
        ("incomplete-trace", clauses, "UNKNOWN", "incomplete"),
    )


def trace_payload(trace):
    scope, condition, confirmation, notification = trace
    return {"scope": scope, "reservation": condition,
            "confirmation_s": confirmation, "notification_s": notification}


def assess(corpus, clauses, disturbance):
    rendered = reconstruct(clauses)
    problems = source_problems(corpus, clauses)
    result = {"rendered": rendered, "provenance_problems": problems,
              "provenance": {clause["id"]: clause["refs"] for clause in clauses},
              "clauses_with_required_provenance": len(clauses) - len(problems)}
    if rendered["status"] == "UNKNOWN":
        return result | {"status": "UNKNOWN", "reason": "unsupported-formal-clause"}
    lines = rendered["lines"]
    if disturbance == "whitespace":
        lines = ["  ".join(line.split()) for line in lines]
    if disturbance == "malformed":
        lines = [lines[0].replace(", inclusive", ""), *lines[1:]]
    if disturbance == "altered-text":
        lines = [lines[0].replace("5 seconds", "7 seconds"), *lines[1:]]
        result["observed_lines"] = lines
    decoded = decode(lines)
    if decoded is None:
        return result | {"status": "UNKNOWN", "reason": "unrecognized-rendering", "observed_lines": lines}

    fidelity = decoded == {clause["id"]: clause for clause in semantic_payload(clauses)}
    if disturbance == "incomplete":
        return result | {"status": "UNKNOWN", "reason": "reservation-outcome-unobserved",
                         "trace": {"scope": "retail", "reservation": None, "observed_through_s": 1}}

    counts = {"newly_allowed": 0, "newly_forbidden": 0}
    witnesses = {}
    for trace in TRACES:
        wanted = independently_expected(trace)
        observed = allows(decoded, trace)
        if wanted != observed:
            direction = "newly_allowed" if observed else "newly_forbidden"
            counts[direction] += 1
            witnesses.setdefault(direction, trace_payload(trace))
    status = "ELIGIBLE"
    if witnesses:
        status = "DIFFERENT"
    elif problems or not fidelity:
        status = "UNKNOWN"
    return result | {"status": status, "trace_count": len(TRACES), "differences": counts,
                     "witnesses": witnesses, "decoded_clauses": len(decoded),
                     "structurally_faithful": fidelity}


def main():
    path = HERE / "corpus.json"
    corpus = json.loads(path.read_text())
    results = {}
    for name, clauses, expected, disturbance in cases(corpus["clauses"]):
        results[name] = assess(corpus, clauses, disturbance) | {"expected_status": expected}
    for name, result in results.items():
        assert result["expected_status"] == result["status"], (name, result)
    model_mutants = [result for name, result in results.items()
                     if result["status"] == "DIFFERENT" and name != "unfaithful-reconstruction"]
    assert all(result["structurally_faithful"] for result in model_mutants)
    assert not results["unfaithful-reconstruction"]["structurally_faithful"]
    print(json.dumps({
        "baseline": BASELINE, "python": platform.python_version(), "horizon_s": HORIZON,
        "file_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                        for name in ("corpus.json", "render.py", "run.py")},
        "trace_count": len(TRACES), "case_counts": {
            status: sum(result["status"] == status for result in results.values())
            for status in ("ELIGIBLE", "DIFFERENT", "UNKNOWN")
        },
        "model_mutants_passing_roundtrip_only": len(model_mutants),
        "model_mutants_passing_roundtrip_and_provenance_only": sum(
            not result["provenance_problems"] for result in model_mutants
        ),
        "results": results,
    }, indent=2))


if __name__ == "__main__":
    main()
