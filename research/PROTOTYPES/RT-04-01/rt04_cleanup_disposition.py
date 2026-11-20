"""Finite cleanup-stack model with resource disposition separated from error.

This COR-13 experiment does not model calls, transfer, or a real OS API. The
caller supplies the disposition guaranteed by each resource API so an error
is not assumed to imply either retention or consumption.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Disposition = Literal["ok", "retained_error", "consumed_error", "indeterminate"]
UnwindPolicy = Literal["continue", "stop"]


@dataclass(frozen=True)
class CleanupStackTrace:
    events: tuple[tuple[str, Disposition], ...]
    released: tuple[str, ...]
    retained: tuple[str, ...]
    consumed_with_error: tuple[str, ...]
    indeterminate: tuple[str, ...]
    not_attempted: tuple[str, ...]
    error_order: tuple[str, ...]


def run_cleanup_stack(
    resources: tuple[str, ...],
    dispositions: dict[str, Disposition],
    *,
    unwind_policy: UnwindPolicy = "continue",
) -> CleanupStackTrace:
    """Attempt cleanup in reverse acquisition order under an explicit policy.

    ``resources`` are listed outermost/first-acquired to innermost/last-
    acquired. A non-``ok`` disposition is an observable cleanup error. Under
    ``continue``, remaining outer cleanups still run; under ``stop``, they do
    not. An ``indeterminate`` disposition never claims the resource is live
    or consumed.
    """
    if (not isinstance(resources, tuple) or any(not isinstance(r, str) or not r for r in resources)
            or len(set(resources)) != len(resources)):
        raise ValueError("resources must be unique non-empty names in a tuple")
    if not isinstance(unwind_policy, str) or unwind_policy not in ("continue", "stop"):
        raise ValueError("unwind_policy must be continue or stop")
    allowed = {"ok", "retained_error", "consumed_error", "indeterminate"}
    if (not isinstance(dispositions, dict) or set(dispositions) != set(resources)
            or any(not isinstance(value, str) or value not in allowed
                   for value in dispositions.values())):
        raise ValueError("dispositions must provide one supported result per resource")

    events: list[tuple[str, Disposition]] = []
    released: list[str] = []
    retained: list[str] = []
    consumed: list[str] = []
    indeterminate: list[str] = []
    errors: list[str] = []
    not_attempted: list[str] = []
    stopped = False

    for resource in reversed(resources):
        if stopped:
            not_attempted.append(resource)
            continue
        result = dispositions[resource]
        events.append((resource, result))
        if result == "ok":
            released.append(resource)
        else:
            errors.append(resource)
            if result == "retained_error":
                retained.append(resource)
            elif result == "consumed_error":
                consumed.append(resource)
            else:
                indeterminate.append(resource)
            if unwind_policy == "stop":
                stopped = True

    return CleanupStackTrace(
        tuple(events), tuple(released), tuple(retained), tuple(consumed),
        tuple(indeterminate), tuple(not_attempted), tuple(errors),
    )
