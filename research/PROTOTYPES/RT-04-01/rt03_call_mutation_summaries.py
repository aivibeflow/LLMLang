"""Finite path oracle for calls with pure, mutating, or incomplete summaries."""
from __future__ import annotations

from itertools import product


Route = tuple[bool, bool]


def routes_for_transition(allowed_updates: frozenset[tuple[bool, bool]]) -> frozenset[Route]:
    """Enumerate branches around a call according to its x-before/x-after relation."""
    return frozenset(
        (before, after)
        for before, after in allowed_updates
    )


def enumerate_call_summary(summary: str) -> frozenset[Route]:
    """Apply a complete or conservative summary for a call that may alias x."""
    if summary == "pure":
        transitions = frozenset((x, x) for x in (False, True))
    elif summary == "toggle":
        transitions = frozenset((x, not x) for x in (False, True))
    elif summary in {"may_write", "unknown"}:
        # A may-alias or incomplete effect summary must not assume x is stable.
        transitions = frozenset(product((False, True), repeat=2))
    else:
        raise ValueError(f"unsupported call summary: {summary!r}")
    return routes_for_transition(transitions)


def name_conflated_routes() -> frozenset[Route]:
    """Incorrectly reuse x's pre-call value for the post-call branch."""
    return frozenset((x, x) for x in (False, True))


if __name__ == "__main__":
    for candidate in ("pure", "toggle", "may_write", "unknown"):
        print(candidate, sorted(enumerate_call_summary(candidate)))
    print("name-conflated", sorted(name_conflated_routes()))
