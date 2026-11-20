"""Compare cleanup policies for a connection and its prepared statements."""

from collections.abc import Iterator
from dataclasses import dataclass
from itertools import product
from typing import Literal


OK, ERROR, BUSY = 0, 1, 5
Policy = Literal["require_empty", "recover_busy", "defer_destroy"]


@dataclass(frozen=True)
class Statement:
    name: str
    owned_here: bool
    failed_step: bool


@dataclass(frozen=True)
class CleanupCall:
    operation: Literal["close", "close_v2", "finalize"]
    statement: str | None
    code: int
    destroyed: bool


@dataclass(frozen=True)
class CleanupResult:
    accepted: bool
    connection: Literal["open", "pending", "destroyed"]
    remaining_statements: tuple[str, ...]
    calls: tuple[CleanupCall, ...] = ()

    @property
    def forwards_connection(self) -> bool:
        return self.accepted and self.connection == "open"

    @property
    def finalize_errors(self) -> tuple[str, ...]:
        return tuple(
            call.statement for call in self.calls
            if call.statement is not None and call.operation == "finalize" and call.code == ERROR
        )


def cleanup(
    policy: Policy, statements: tuple[Statement, ...], *, close_first: bool,
) -> CleanupResult:
    """Run one caller over a complete, fixed set of live statement capabilities.

    The caller finalizes its statements once. A busy close can retry only
    when this removes all dependencies. External owners keep their statements.
    """
    if policy not in ("require_empty", "recover_busy", "defer_destroy"):
        raise ValueError("unsupported close policy")
    if type(close_first) is not bool:
        raise ValueError("expected a Boolean close order")
    for statement in statements:
        if not isinstance(statement.name, str) or not statement.name:
            raise ValueError("each statement needs a name")
        if type(statement.owned_here) is not bool or type(statement.failed_step) is not bool:
            raise ValueError("expected Boolean statement flags")
    live = {statement.name: statement for statement in statements}
    if len(live) != len(statements):
        raise ValueError("statement names must be unique")

    local = tuple(statement for statement in statements if statement.owned_here)
    count_at_close = len(statements) if close_first else len(statements) - len(local)
    if policy == "require_empty" and count_at_close:
        return CleanupResult(False, "open", tuple(live))

    calls: list[CleanupCall] = []
    retired = False

    def finalize_local() -> None:
        for statement in local:
            del live[statement.name]
            code = ERROR if statement.failed_step else OK
            calls.append(CleanupCall("finalize", statement.name, code, retired and not live))

    def close_connection() -> int:
        nonlocal retired
        deferred = policy == "defer_destroy"
        code = BUSY if live and not deferred else OK
        retired = code == OK
        operation = "close_v2" if deferred else "close"
        calls.append(CleanupCall(operation, None, code, retired and not live))
        return code

    if close_first:
        initial_close = close_connection()
        finalize_local()
        if initial_close == BUSY and not live:
            close_connection()
    else:
        finalize_local()
        close_connection()

    phase = "open" if not retired else "pending" if live else "destroyed"
    return CleanupResult(True, phase, tuple(live), tuple(calls))


def statement_fixtures() -> Iterator[tuple[Statement, ...]]:
    """Enumerate all ownership and step outcome assignments for up to three statements."""
    choices = tuple(product((False, True), repeat=2))
    for size in range(4):
        for fields in product(choices, repeat=size):
            yield tuple(Statement(f"s{i}", owned_here, failed) for i, (owned_here, failed) in enumerate(fields))
