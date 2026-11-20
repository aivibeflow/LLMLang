"""Finite store-buffering litmus enumerator for two candidate memory profiles.

This is an abstract comparison, not an implementation of C++, Rust, or Go.
"""
from itertools import permutations


def sequentially_consistent_outcomes():
    """Enumerate values under one global order preserving each thread's order."""
    # Initial writes precede all events. W_x, R_y are thread 1; W_y, R_x thread 2.
    events = ("Wx", "Ry", "Wy", "Rx")
    outcomes = set()
    for order in permutations(events):
        position = {event: i for i, event in enumerate(order)}
        if position["Wx"] > position["Ry"] or position["Wy"] > position["Rx"]:
            continue
        x = y = 0
        reads = {}
        for event in order:
            if event == "Wx":
                x = 1
            elif event == "Wy":
                y = 1
            elif event == "Rx":
                reads["rx"] = x
            else:
                reads["ry"] = y
        outcomes.add((reads["rx"], reads["ry"]))
    return outcomes


def per_location_atomic_outcomes():
    """Abstract independently ordered locations; each read sees init or store."""
    # Each load can observe the initial value or the other thread's store; this
    # profile intentionally has no cross-location global order constraint.
    return {(rx, ry) for rx in (0, 1) for ry in (0, 1)}


def message_passing_outcomes(synchronized):
    """Enumerate a publication litmus under stated happens-before premises.

    Writer stores payload before flag. Reader loads flag before payload. When
    ``synchronized`` is true, observing flag=1 creates a synchronizes-with edge
    and therefore forbids a subsequent payload read of the initial value.
    Without that edge, all independent read values are admitted in this toy
    model. Data races and weak memory rules are intentionally out of scope.
    """
    outcomes = set()
    for flag in (0, 1):
        for payload in (0, 1):
            if synchronized and flag == 1 and payload == 0:
                continue
            outcomes.add((flag, payload))
    return outcomes
