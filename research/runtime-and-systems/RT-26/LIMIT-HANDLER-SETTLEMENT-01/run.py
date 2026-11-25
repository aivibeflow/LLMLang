"""Compare typed limit-handler settlement policies on deterministic schedules."""

from dataclasses import asdict, dataclass, replace
from itertools import product
import hashlib
import json
import platform
from pathlib import Path

BASELINE = "2bf61c4bc5aafa02e8489292da27ed1ff424e825"
POLICIES = ("override", "fresh-hard-check", "exact-once")


@dataclass(frozen=True)
class State:
    scope: str = "task-A"
    generation: int = 1
    soft: int = 4
    hard: int = 8
    held: int = 4
    cancelled: bool = False


@dataclass(frozen=True)
class Event:
    event_id: int
    scope: str
    generation: int
    requested: int
    observed_held: int
    soft: int
    hard: int
    deadline: int


@dataclass(frozen=True)
class Proposal:
    action: str
    units: int = 0
    handler_steps: int = 1
    tick: int = 1


def issue(state, requested=2, event_id=1):
    assert requested > 0 and state.held + requested > state.soft
    return Event(event_id, state.scope, state.generation, requested, state.held, state.soft, state.hard, 3)


def decision(policy, state, event, proposal, prior):
    if policy == "exact-once" and prior is not None:
        if prior["event"] != asdict(event) or prior["proposal"] != asdict(proposal):
            return state, "decision-mismatch", False
        return state, prior["outcome"], True
    if policy == "exact-once":
        if (state.scope, state.generation) != (event.scope, event.generation):
            return state, "stale-event", False
    if proposal.tick > event.deadline:
        return state, "deadline", False
    if proposal.handler_steps > 2:
        return state, "handler-budget", False
    if proposal.action == "fail":
        return state, "handler-failure", False
    if proposal.action in {"pause", "escalate"}:
        return state, proposal.action, False
    if proposal.action == "cancel":
        return replace(state, cancelled=True), "cancelled", False
    if proposal.action not in {"resume", "degrade"}:
        return state, "unknown-action", False
    requested = event.requested
    if proposal.action == "degrade":
        if not 0 < proposal.units < requested:
            return state, "invalid-degrade", False
        requested = proposal.units
    if policy != "override":
        if state.cancelled:
            return state, "scope-cancelled", False
        if state.held + requested > state.hard:
            return state, "hard-limit", False
    return replace(state, held=state.held + requested), "reserved", False


def run_schedule(policy, initial, before, first, second=None):
    event = issue(initial)
    after, first_status, replayed = decision(policy, before, event, first, None)
    assert not replayed
    receipt = {"event": asdict(event), "proposal": asdict(first), "outcome": first_status}
    after_retry, retry_status, replayed = decision(
        policy, after, event, second if second is not None else first, receipt,
    )
    return {
        "before": asdict(before), "initial": {"outcome": first_status, "state": asdict(after)},
        "receipt": receipt,
        "retry": {"outcome": retry_status, "state": asdict(after_retry), "replayed": replayed},
    }


def checks():
    initial = State()
    resume = Proposal("resume")
    controls = {
        "resume": (initial, resume, None, ("reserved", "reserved", "reserved"), 6),
        "peer-uses-headroom": (replace(initial, held=7), resume, None,
                               ("reserved", "hard-limit", "hard-limit"), 7),
        "hard-limit-reconfigured": (replace(initial, hard=5, generation=2), resume, None,
                                    ("reserved", "hard-limit", "stale-event"), 4),
        "same-cap-generation-change": (replace(initial, generation=2), resume, None,
                                       ("reserved", "reserved", "stale-event"), 4),
        "different-task-same-limit": (replace(initial, scope="task-B"), resume, None,
                                      ("reserved", "reserved", "stale-event"), 4),
        "live-cancellation": (replace(initial, cancelled=True), resume, None,
                              ("reserved", "scope-cancelled", "scope-cancelled"), 4),
        "bounded-degrade": (replace(initial, held=7), Proposal("degrade", units=1), None,
                            ("reserved", "reserved", "reserved"), 8),
        "invalid-degrade": (initial, Proposal("degrade", units=2), None,
                            ("invalid-degrade",) * 3, 4),
        "pause-then-different-decision": (initial, Proposal("pause"), resume, ("pause",) * 3, 4),
        "cancel-retains-held-units": (initial, Proposal("cancel"), None, ("cancelled",) * 3, 4),
        "escalate": (initial, Proposal("escalate"), None, ("escalate",) * 3, 4),
        "handler-fails": (initial, Proposal("fail"), None, ("handler-failure",) * 3, 4),
        "handler-misses-deadline": (initial, Proposal("resume", tick=4), None, ("deadline",) * 3, 4),
        "handler-exhausts-own-budget": (initial, Proposal("resume", handler_steps=3), None,
                                        ("handler-budget",) * 3, 4),
    }
    examples = {}
    for name, (before, first, second, statuses, expected_held) in controls.items():
        rows = {policy: run_schedule(policy, initial, before, first, second) for policy in POLICIES}
        assert tuple(rows[policy]["initial"]["outcome"] for policy in POLICIES) == statuses
        exact = rows["exact-once"]
        assert exact["initial"]["state"]["held"] == expected_held
        assert exact["retry"]["state"] == exact["initial"]["state"]
        if second is None:
            assert exact["retry"]["replayed"] and exact["retry"]["outcome"] == statuses[-1]
        else:
            assert not exact["retry"]["replayed"] and exact["retry"]["outcome"] == "decision-mismatch"
        examples[name] = rows
    assert examples["resume"]["fresh-hard-check"]["retry"]["state"]["held"] == 8

    second = issue(initial, event_id=2)
    first_receipt = examples["resume"]["exact-once"]["receipt"]
    after_first = State(**examples["resume"]["exact-once"]["initial"]["state"])
    wrong = decision("exact-once", after_first, second, resume, first_receipt)
    right = decision("exact-once", after_first, second, resume, None)
    assert wrong == (after_first, "decision-mismatch", False)
    assert right == (replace(after_first, held=8), "reserved", False)
    examples["distinct-identical-looking-events"] = {
        "event": asdict(second), "supplied_other_event_receipt": first_receipt,
        "wrong_receipt": {"held": wrong[0].held, "outcome": wrong[1]},
        "no_prior_receipt": {"held": right[0].held, "outcome": right[1]},
    }

    finite = []
    for hard, held, cancelled, repeated in product(range(4, 10), range(4, 10), (False, True),
                                                   (False, True)):
        if held > hard:
            continue
        start = replace(initial, hard=hard)
        current = replace(start, held=held, cancelled=cancelled)
        event = issue(start)
        outcomes = {}
        for policy in POLICIES:
            after, outcome, _ = decision(policy, current, event, resume, None)
            if repeated:
                record = {"event": asdict(event), "proposal": asdict(resume), "outcome": outcome}
                after, _, _ = decision(policy, after, event, resume, record)
            exact_admitted = not cancelled and held + event.requested <= hard
            expected_held = held + (event.requested if exact_admitted else 0)
            if policy == "exact-once":
                assert after.held == expected_held <= hard
                assert after.cancelled == cancelled
            outcomes[policy] = {
                "held": after.held, "over_hard": after.held > hard,
                "cancelled_reservation": cancelled and after.held > held,
                "duplicate_reservation": after.held - held > event.requested,
            }
        finite.append({"hard": hard, "held": held, "cancelled": cancelled, "repeated": repeated,
                       "policies": outcomes})
    fields = ("over_hard", "cancelled_reservation", "duplicate_reservation")
    totals = {
        policy: {name: sum(row["policies"][policy][name] for row in finite) for name in fields}
        for policy in POLICIES
    }
    assert len(finite) == 84
    assert totals["exact-once"] == dict.fromkeys(fields, 0)
    assert max(row["policies"]["override"]["held"] - row["hard"] for row in finite) == 4
    return examples, finite, totals


def main():
    examples, finite, totals = checks()
    metadata = {
        "baseline": BASELINE, "python": platform.python_version(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "unit": "reservation tokens", "examples": examples, "counts": totals,
    }
    print(json.dumps(metadata, indent=2).removesuffix("\n}") + ',\n  "finite_cases": [')
    print(",\n".join("    " + json.dumps(row) for row in finite))
    print("  ]\n}")


if __name__ == "__main__":
    main()
