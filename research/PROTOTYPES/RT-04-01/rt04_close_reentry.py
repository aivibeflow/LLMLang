"""Compare close policies across synchronous reentry and dependent kinds."""

from collections.abc import Iterator
from dataclasses import dataclass
from itertools import product
from typing import Literal, get_args

from rt04_sqlite_recovery import BUSY, OK


CallbackPolicy = Literal["lock_only", "reserve_close", "inspect_again"]
CallbackAction = Literal["skipped", "preserved", "retained", "refused"]
Dependent = Literal["none", "statement", "blob", "backup"]
CloseCall = Literal["close", "close_v2"]


@dataclass(frozen=True)
class CallbackCase:
    policy: CallbackPolicy
    initially_live: bool
    callback_prepares: bool


@dataclass(frozen=True)
class CallbackObservation:
    initial_count: int
    action: CallbackAction
    count_after_callback: int
    close_code: int | None


@dataclass(frozen=True)
class CoverageObservation:
    statement_count: int
    close_code: int
    destroyed_at_close: bool
    destroyed_after_release: bool


def callback_cases() -> Iterator[CallbackCase]:
    for policy, initially_live, prepares in product(get_args(CallbackPolicy), (False, True), (False, True)):
        yield CallbackCase(policy, initially_live, prepares)


def predict_callback(case: CallbackCase) -> CallbackObservation:
    if case.initially_live:
        return CallbackObservation(1, "skipped", 1, None)
    if not case.callback_prepares:
        return CallbackObservation(0, "preserved", 0, OK)
    if case.policy == "reserve_close":
        return CallbackObservation(0, "refused", 0, OK)
    code = None if case.policy == "inspect_again" else BUSY
    return CallbackObservation(0, "retained", 1, code)


def coverage_cases() -> Iterator[tuple[Dependent, CloseCall]]:
    yield from product(get_args(Dependent), get_args(CloseCall))


def predict_coverage(dependent: Dependent, operation: CloseCall) -> CoverageObservation:
    """Project the SQLite 3.46.1 statement view for the four fixtures."""
    count = int(dependent in ("statement", "blob"))
    empty = dependent == "none"
    if operation == "close_v2":
        return CoverageObservation(count, OK, empty, True)
    return CoverageObservation(count, OK if empty else BUSY, empty, empty)
