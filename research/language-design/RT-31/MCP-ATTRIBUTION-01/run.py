"""Compare MCP failure attribution on finite, synthetic event histories."""

from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import permutations, product
import json
from pathlib import Path


PRODUCER = {
    "model": "source-validator",
    "task-context": "context-validator",
    "toolchain": "differential-checker",
    "environment": "environment-probe",
    "terminal": "coordinator",
}
CAUSES = tuple(role for role in PRODUCER if role != "terminal")


@dataclass(frozen=True)
class Binding:
    session: str = "session-1"
    turn: int = 3
    attempt: int = 2
    snapshot: str = "snapshot-7"
    toolchain: str = "build-4"


@dataclass(frozen=True)
class Event:
    binding: Binding
    id: str
    role: str
    producer: str
    verdict: str


def event(binding, role, verdict):
    return Event(binding, f"{binding.turn}/{binding.attempt}/{role}", role, PRODUCER[role], verdict)


def checked_attribution(binding, events):
    reports = {role: set() for role in PRODUCER}
    for observed in events:
        if observed.binding == binding and observed.role in reports:
            expected = event(binding, observed.role, observed.verdict)
            if observed == expected:
                reports[observed.role].add(observed.verdict)
    causes = tuple(role for role in CAUSES if reports[role] == {"fail"})
    missing = tuple(role for role in CAUSES if reports[role] not in ({"fail"}, {"pass"}))
    unsealed = reports["terminal"] != {"sealed"}
    return causes, missing, unsealed


def single_cause(events):
    observed = next((item.role for item in events
                     if item.role in CAUSES and item.verdict == "fail"), None)
    return (() if observed is None else (observed,)), (), False


def last_session_failure(binding, events):
    same_session = (item for item in reversed(events) if item.binding.session == binding.session)
    return single_cause(same_session)


def first_attempt_failure(binding, events):
    same_attempt = (item for item in events if
                    (item.binding.session, item.binding.turn, item.binding.attempt) ==
                    (binding.session, binding.turn, binding.attempt))
    return single_cause(same_attempt)


def variants(binding, events):
    previous = event(replace(binding, attempt=1), "model", "fail")
    wrong_build = event(replace(binding, toolchain="build-3"), "task-context", "fail")
    wrong_snapshot = event(replace(binding, snapshot="snapshot-6"), "environment", "fail")
    wrong_producer = replace(event(binding, "environment", "fail"), producer="external-message")
    conflicting = replace(events[2], verdict="pass" if events[2].verdict == "fail" else "fail")
    return {
        "complete": events,
        "unsealed": events[:-1],
        "missing-model-check": events[1:],
        "conflicting-toolchain-check": (*events, conflicting),
        "repeated-environment-check": (*events, events[3]),
        "previous-attempt-failure": (*events, previous),
        "wrong-build-failure": (*events, wrong_build),
        "wrong-snapshot-failure": (*events, wrong_snapshot),
        "wrong-producer-failure": (*events, wrong_producer),
    }


def oracle(flags, variant):
    untrusted_slot = {"missing-model-check": "model", "conflicting-toolchain-check": "toolchain"}
    unknown = untrusted_slot.get(variant)
    causes = tuple(role for role, failed in zip(CAUSES, flags, strict=True)
                   if failed and role != unknown)
    return causes, (unknown,) if unknown else (), variant == "unsealed"


def tally():
    binding = Binding()
    summaries = {}
    examples = {}
    for flags in product((False, True), repeat=len(CAUSES)):
        events = tuple(event(binding, role, "fail" if failed else "pass")
                       for role, failed in zip(CAUSES, flags, strict=True))
        terminal = event(binding, "terminal", "sealed")
        for variant, inputs in variants(binding, (*events, terminal)).items():
            expected = oracle(flags, variant)
            counts = summaries.setdefault(variant, Counter())
            for schedule in set(permutations(inputs)):
                exact = checked_attribution(binding, schedule)
                if exact != expected:
                    raise AssertionError((flags, variant, schedule, exact, expected))
                last = last_session_failure(binding, schedule)
                first = first_attempt_failure(binding, schedule)
                counts["schedules"] += 1
                counts["exact_match"] += 1
                counts["last_session_match"] += last == expected
                counts["first_attempt_match"] += first == expected
                counts["expected_multiple_causes"] += len(expected[0]) > 1
                counts["expected_unknown"] += bool(expected[1] or expected[2])
            if variant not in examples and (
                flags == (False, False, False, False) and variant not in
                {"complete", "unsealed", "missing-model-check", "conflicting-toolchain-check"}
                or flags == (True, False, True, False)
            ):
                examples[variant] = {
                    "expected": expected,
                    "last_session": last_session_failure(binding, inputs),
                    "first_attempt": first_attempt_failure(binding, inputs),
                }

    totals = sum(summaries.values(), Counter())
    return {
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "fault_masks": 2**len(CAUSES),
        "variants": summaries,
        "totals": totals,
        "examples": examples,
    }


if __name__ == "__main__":
    print(json.dumps(tally(), indent=2, sort_keys=True))
