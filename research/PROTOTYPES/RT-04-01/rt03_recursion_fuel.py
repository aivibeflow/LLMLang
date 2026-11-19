"""Small fuel-counting model for recursive RT-03 behavior.

This models one source-level countdown function, not LLMLang syntax or a
compiler. Each abstract transition consumes one unit of source fuel. The
separate divergent loop model demonstrates that finite fuel exhaustion alone
cannot classify divergence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Status = Literal["returned", "fuel_exhausted"]
Event = tuple[str, int | None]


@dataclass(frozen=True)
class Evaluation:
    status: Status
    value: int | None
    fuel_used: int
    fuel_remaining: int
    events: tuple[Event, ...]
    next_transition: str | None
    may_diverge: bool


def _spend(fuel: int, used: int, events: list[Event], event: Event) -> tuple[int, int] | None:
    if used >= fuel:
        return None
    events.append(event)
    return used + 1, fuel - used - 1


def run_countdown(n: int, fuel: int) -> Evaluation:
    """Run ``countdown(n) = 0 if n == 0 else countdown(n-1) + 1``.

    Abstract source transitions are function entry, condition test, decrement,
    and each addition during return. This call-by-value recursive definition
    uses ``4*n + 2`` units when it returns for non-negative ``n``.
    """
    if type(n) is not int or n < 0:
        raise ValueError("n must be a non-negative integer")
    if type(fuel) is not int or fuel < 0:
        raise ValueError("fuel must be a non-negative integer")

    used = 0
    remaining = fuel
    events: list[Event] = []
    pending_adds = 0
    current = n

    while True:
        for event in (("call_enter", current), ("condition_test", current)):
            paid = _spend(fuel, used, events, event)
            if paid is None:
                return Evaluation("fuel_exhausted", None, used, remaining,
                                  tuple(events), event[0], False)
            used, remaining = paid

        if current == 0:
            value = 0
            break

        event = ("decrement", current)
        paid = _spend(fuel, used, events, event)
        if paid is None:
            return Evaluation("fuel_exhausted", None, used, remaining,
                              tuple(events), event[0], False)
        used, remaining = paid
        current -= 1
        pending_adds += 1

    while pending_adds:
        event = ("return_add", value)
        paid = _spend(fuel, used, events, event)
        if paid is None:
            return Evaluation("fuel_exhausted", None, used, remaining,
                              tuple(events), event[0], False)
        used, remaining = paid
        value += 1
        pending_adds -= 1

    return Evaluation("returned", value, used, remaining, tuple(events), None, False)


def run_divergent_loop(fuel: int) -> Evaluation:
    """Run a self-recursive loop under finite abstract source fuel.

    The result is fuel exhaustion for every finite budget; this observation by
    itself cannot distinguish true divergence from a terminating function
    requiring more fuel. ``may_diverge`` is independent static information.
    """
    if type(fuel) is not int or fuel < 0:
        raise ValueError("fuel must be a non-negative integer")
    events: list[Event] = []
    used = 0
    while used < fuel:
        events.append(("recursive_call", None))
        used += 1
    return Evaluation("fuel_exhausted", None, used, 0, tuple(events),
                      "recursive_call", True)
