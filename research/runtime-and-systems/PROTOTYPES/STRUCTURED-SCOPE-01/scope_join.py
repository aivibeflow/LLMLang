"""Finite schedule comparison for the lifetime of a nested task scope."""

from collections import Counter
from dataclasses import dataclass
from itertools import permutations


TASKS = ("child", "grandchild", "sibling")
EVENTS = ("exit", "child-body", "grandchild-body", "sibling-body",
          "grandchild-cleanup", "sibling-cleanup", "poll")
POLICIES = ("request", "direct-bodies", "transitive-join")


@dataclass(frozen=True)
class Terminal:
    failures: tuple[str, ...]
    outstanding_loans: tuple[str, ...]


def observe(schedule, policy):
    """Return the first terminal observation, if a poll may publish one."""
    if policy not in POLICIES:
        raise ValueError("unknown scope publication policy")
    requested = False
    bodies = set()
    released = set()
    failures = set()
    loans = {"grandchild", "sibling"}
    for event in schedule:
        if event == "exit":
            requested = True
        elif event == "poll":
            if requested and (
                policy == "request"
                or (policy == "direct-bodies" and {"child", "sibling"} <= bodies)
                or (policy == "transitive-join" and set(TASKS) <= released)
            ):
                return Terminal(tuple(task for task in TASKS if task in failures),
                                tuple(sorted(loans - released)))
        else:
            task, phase = event.split("-")
            if phase == "body":
                bodies.add(task)
                if task == "sibling":
                    failures.add(task)
            elif phase == "cleanup":
                if task == "grandchild":
                    # Cleanup failed but returned the tracked loan.
                    failures.add(task)
                released.add(task)
            else:
                raise ValueError(f"unknown event {event}")

            # A structured child has joined only after its nested scope joins.
            if "child" in bodies and "grandchild" in released:
                released.add("child")
    return None


def schedules():
    for schedule in permutations(EVENTS):
        if (schedule.index("grandchild-body") < schedule.index("grandchild-cleanup")
                and schedule.index("sibling-body") < schedule.index("sibling-cleanup")):
            yield schedule


def oracle(schedule):
    """Check obligations independently at the scheduled poll."""
    required = {"exit", "child-body", "grandchild-cleanup", "sibling-cleanup"}
    complete = required <= set(schedule[:schedule.index("poll")])
    return Terminal(("grandchild", "sibling"), ()) if complete else None


def run():
    cases = list(schedules())
    expected_terminal = Terminal(("grandchild", "sibling"), ())
    for policy in POLICIES:
        counts = Counter()
        for schedule in cases:
            result = observe(schedule, policy)
            expected = oracle(schedule)
            counts["blocked"] += result is None
            counts["published"] += result is not None
            counts["live_loans"] += result is not None and bool(result.outstanding_loans)
            counts["lost_failure"] += result is not None and result.failures != expected_terminal.failures
            counts["oracle_mismatch"] += result != expected
            replay = observe((*schedule, "poll"), policy)
            assert replay is not None
            if policy == "transitive-join":
                assert replay == expected_terminal
        print(policy, dict(sorted(counts.items())))
        if policy == "transitive-join":
            assert counts["oracle_mismatch"] == 0 and counts["published"] == 180
        else:
            assert counts["live_loans"] > 0 and counts["lost_failure"] > 0

    witness = ("exit", "child-body", "sibling-body", "sibling-cleanup",
               "poll", "grandchild-body", "grandchild-cleanup")
    assert observe(witness, "direct-bodies") == Terminal(("sibling",), ("grandchild",))
    assert observe(witness, "transitive-join") is None
    assert observe((*witness, "poll"), "transitive-join") == expected_terminal
    uncooperative = tuple(event for event in witness if not event.startswith("grandchild-"))
    assert observe((*uncooperative, "poll", "poll"), "transitive-join") is None
    return len(cases)


if __name__ == "__main__":
    print(f"{run()} schedules per policy")
