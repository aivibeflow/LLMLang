"""Probe cleanup reserves across a nested LIFO resource stack.

The model charges a fixed cost per release and compares one shared reserve
against a per-scope reserve. It keeps completed body effects, cleanup errors,
unattempted scopes, and retained resources as separate observations. These are
candidate accounting rules, not LLMLang semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ReserveMode = Literal["shared", "per_scope"]


@dataclass(frozen=True)
class Cleanup:
    resource: str
    cost: int
    fails: bool = False


@dataclass(frozen=True)
class StackObservation:
    reserve_mode: ReserveMode
    fuel_exhausted: bool
    reserve_initial: int
    reserve_spent: int
    effects: tuple[str, ...]
    cleanup_attempts: tuple[tuple[str, str], ...]
    cleanup_errors: tuple[str, ...]
    cleanup_blocked: tuple[str, ...]
    retained_resources: tuple[tuple[str, str], ...]


def unwind_with_reserve(
    cleanups: tuple[Cleanup, ...] | list[Cleanup],
    *,
    reserve_mode: ReserveMode,
    reserve: int,
    completed_effects: tuple[str, ...] = ("write:recorded",),
) -> StackObservation:
    """Unwind frames supplied outermost first after ordinary fuel is spent.

    In ``shared`` mode, ``reserve`` is one total cleanup budget. In
    ``per_scope`` mode, each resource receives a reserve of that size. A
    blocked inner frame blocks outer frames to retain strict LIFO order.
    Failed release is attempted, consumes its fixed cost, retains that
    resource, and does not suppress outer cleanup while reserve remains.
    """
    frames = tuple(cleanups)
    if reserve_mode not in {"shared", "per_scope"}:
        raise ValueError(f"unsupported reserve mode: {reserve_mode}")
    if type(reserve) is not int or reserve < 0:
        raise ValueError("reserve must be a non-negative integer")
    if any(not isinstance(frame, Cleanup) for frame in frames):
        raise ValueError("cleanups must contain Cleanup values")
    if any(not isinstance(frame.resource, str) or not frame.resource for frame in frames):
        raise ValueError("resource names must be non-empty strings")
    if len({frame.resource for frame in frames}) != len(frames):
        raise ValueError("resource names must be unique")
    if any(type(frame.cost) is not int or frame.cost <= 0 for frame in frames):
        raise ValueError("cleanup cost must be a positive integer")
    if any(type(frame.fails) is not bool for frame in frames):
        raise ValueError("cleanup failure flags must be booleans")
    if any(not isinstance(effect, str) for effect in completed_effects):
        raise ValueError("effects must be strings")

    spent = 0
    attempts: list[tuple[str, str]] = []
    errors: list[str] = []
    blocked: list[str] = []
    retained: dict[str, str] = {}

    for index, frame in enumerate(reversed(frames)):
        available = reserve - spent if reserve_mode == "shared" else reserve
        if available < frame.cost:
            newly_blocked = tuple(
                item.resource for item in reversed(frames[:len(frames) - index])
            )
            blocked.extend(newly_blocked)
            retained.update({resource: "cleanup_unattempted" for resource in newly_blocked})
            # The slice above includes the blocked frame and all outer frames.
            break

        spent += frame.cost
        result = "error" if frame.fails else "ok"
        attempts.append((frame.resource, result))
        if frame.fails:
            errors.append(frame.resource)
            retained[frame.resource] = "release_failed"

    return StackObservation(
        reserve_mode,
        True,
        reserve * len(frames) if reserve_mode == "per_scope" else reserve,
        spent,
        tuple(completed_effects),
        tuple(attempts),
        tuple(errors),
        tuple(blocked),
        tuple((frame.resource, retained[frame.resource])
              for frame in frames if frame.resource in retained),
    )


def reserve_sweep() -> tuple[StackObservation, ...]:
    """Compare a two-frame stack with costs outer=1 and inner=3."""
    frames = (Cleanup("outer", 1), Cleanup("inner", 3))
    shared = tuple(unwind_with_reserve(frames, reserve_mode="shared", reserve=value)
                   for value in (0, 2, 3, 4))
    per_scope = tuple(unwind_with_reserve(frames, reserve_mode="per_scope", reserve=value)
                      for value in (0, 1, 3))
    failure = unwind_with_reserve(
        (Cleanup("outer", 1), Cleanup("inner", 3, fails=True)),
        reserve_mode="shared", reserve=4,
    )
    return (*shared, *per_scope, failure)


if __name__ == "__main__":
    for observation in reserve_sweep():
        print(observation)
