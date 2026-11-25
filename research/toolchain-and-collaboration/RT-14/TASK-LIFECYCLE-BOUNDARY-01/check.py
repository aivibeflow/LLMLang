"""Compare a status-only Task Context with a revision-bound lifecycle."""

from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform


ACTIONS = {
    "create": (("absent",), "draft"),
    "clarify": (("draft", "clarifying"), "clarifying"),
    "plan": (("draft", "clarifying"), "planned"),
    "run": (("planned",), "running"),
    "block": (("running",), "blocked"),
    "fail": (("running",), "failed"),
    "retry": (("blocked", "failed"), "planned"),
    "delegate": (("running",), "running"),
    "decompose": (("planned",), "planned"),
    "review": (("running",), "reviewing"),
    "handoff": (("reviewing",), "handed-off"),
    "complete": (("reviewing", "handed-off"), "completed"),
    "cancel": (("draft", "clarifying", "planned", "running", "blocked", "failed", "reviewing", "handed-off"),
               "cancelled"),
}
PHASES = sorted({phase for starts, finish in ACTIONS.values() for phase in (*starts, finish)})
EVIDENCE_ACTIONS = {"plan", "delegate", "decompose", "review", "handoff", "complete"}


@dataclass(frozen=True)
class State:
    phase: str
    revision: int = 3
    attempt: int = 5


def apply_exact(state, action, expected_revision, expected_attempt, evidence):
    if (state.revision, state.attempt) != (expected_revision, expected_attempt):
        return "stale", state
    phases, destination = ACTIONS[action]
    if state.phase not in phases:
        return "invalid-transition", state
    if action in EVIDENCE_ACTIONS and not evidence:
        return "missing-evidence", state
    return "accepted", State(destination, state.revision + int(action == "clarify"),
                             state.attempt + int(action == "retry"))


def state_only(state, action):
    phases, destination = ACTIONS[action]
    return (state.phase in phases, destination)


def run():
    counts = Counter()
    comparator = Counter()
    for phase, action, current_rev, current_attempt, evidence in product(
        PHASES, ACTIONS, (False, True), (False, True), (False, True)
    ):
        state = State(phase)
        exact, updated = apply_exact(state, action, 3 if current_rev else 2,
                                    5 if current_attempt else 4, evidence)
        phase_allowed, destination = state_only(state, action)
        expected = phase_allowed and current_rev and current_attempt and (evidence or action not in EVIDENCE_ACTIONS)
        assert (exact == "accepted") == expected
        assert updated.phase == (destination if expected else phase)
        if not expected:
            assert updated == state
        counts[exact] += 1
        if phase_allowed and not expected:
            comparator["unsafe_status_only_admissions"] += 1

    state = State("absent")
    sequence = ("create", "clarify", "plan", "decompose", "run", "delegate", "block",
                "retry", "run", "fail", "retry", "run", "review", "handoff", "complete")
    observed = []
    for action in sequence:
        status, state = apply_exact(state, action, state.revision, state.attempt, True)
        assert status == "accepted"
        observed.append([action, state.phase, state.revision, state.attempt])
    assert state == State("completed", 4, 7)
    assert apply_exact(state, "cancel", state.revision, state.attempt, True)[0] == "invalid-transition"
    assert apply_exact(replace(state, phase="cancelled"), "complete", state.revision,
                       state.attempt, True)[0] == "invalid-transition"
    return {"python": platform.python_version(), "outcomes": counts, "states": sum(counts.values()),
            "comparison": comparator, "successful_lifecycle": observed,
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
