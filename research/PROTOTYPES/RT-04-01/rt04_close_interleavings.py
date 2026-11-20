"""Enumerate one statement producer around observation, validation, and close."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

from rt04_sqlite_recovery import BUSY, OK


Policy = Literal["split_snapshot", "split_version", "shared_guard", "alias_guard"]
Placement = Literal["before_snapshot", "after_snapshot", "after_validation", "after_close"]


@dataclass(frozen=True)
class Schedule:
    policy: Policy
    prepare_at: Placement


@dataclass(frozen=True)
class Observation:
    snapshot_size: int
    version_matched: bool | None
    close_code: int | None
    prepared: bool


def schedules() -> Iterator[Schedule]:
    """Place one prepare in each available gap of the closer's sequence."""
    placements: dict[Policy, tuple[Placement, ...]] = {
        "split_snapshot": ("before_snapshot", "after_snapshot", "after_close"),
        "split_version": ("before_snapshot", "after_snapshot", "after_validation", "after_close"),
        "shared_guard": ("before_snapshot", "after_close"),
        # The independent alias can enter during the guard. The fixture
        # schedules that alias only before retirement of the connection.
        "alias_guard": ("before_snapshot", "after_snapshot"),
    }
    for policy, orderings in placements.items():
        for placement in orderings:
            yield Schedule(policy, placement)


def predict(schedule: Schedule) -> Observation:
    """Evaluate an admitted schedule with one persistent dependent."""
    known_live = schedule.prepare_at == "before_snapshot"
    prepared = schedule.prepare_at != "after_close"
    if known_live:
        return Observation(1, None, None, prepared)

    matches = None
    if schedule.policy == "split_version":
        matches = schedule.prepare_at != "after_snapshot"
        if not matches:
            return Observation(0, False, None, prepared)

    return Observation(0, matches, BUSY if prepared else OK, prepared)
