"""Compare four close policies at the same owned-result call boundary."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal, get_args

from rt04_close_evidence import CloseFact, Execution, analyze, executions, parse
from rt04_owned_call_match import Obligation, ResultCase
from rt04_sqlite_recovery import CleanupResult, Statement, cleanup


ClosePolicy = Literal["source_proof", "checked_snapshot", "recover_busy", "defer_destroy"]
Refusal = Literal["stale_snapshot", "nonempty_snapshot"]

SOURCE = """\
db = connect()
inspect(db)
if registered_owner:
    registered = prepare(db)
if opaque_call:
    foreign(db)
if run_local:
    local = prepare(db)
    finalize(local)
if refresh:
    inspect(db)
close(db)
"""


@dataclass(frozen=True)
class Fixture:
    proof: CloseFact
    state: Execution
    statements: tuple[Statement, ...]


@dataclass(frozen=True)
class CallBoundary:
    result: CleanupResult | None
    refusal: Refusal | None = None

    @property
    def shape(self) -> ResultCase | None:
        """Describe the result a caller can forward after source admission."""
        if self.result is None:
            return None
        if self.result.forwards_connection:
            return ResultCase(self.refusal or "busy", frozenset({Obligation("handle", "retained")}))
        return ResultCase(f"closed_{self.result.connection}")


def fixtures() -> Iterator[Fixture]:
    """Use a registered outside owner, a foreign call, and optional local failure."""
    program = parse(SOURCE)
    proofs = {fact.inputs: fact for fact in analyze(program)}
    for state in executions(program):
        flags = dict(state.inputs)
        outside = []
        # The wrapper registers this dependency in its summary. The fixture
        # supplies the separate owner of the registered statement.
        if flags["registered_owner"]:
            outside.append(Statement("registered", False, False))
        if any(state.foreign_creations):
            outside.append(Statement("foreign", False, False))
        proof = proofs[state.inputs]
        if flags["run_local"]:
            for failed_step in (False, True):
                yield Fixture(proof, state, (*outside, Statement("local", True, failed_step)))
        else:
            yield Fixture(proof, state, tuple(outside))


def compare(policy: ClosePolicy, fixture: Fixture) -> CallBoundary:
    """Compose the source/snapshot fact with the resource and result model."""
    if policy not in get_args(ClosePolicy):
        raise ValueError("unsupported close policy")
    if policy == "source_proof":
        if fixture.proof.verdict != "PROVEN_EMPTY":
            return CallBoundary(None)
        result = cleanup("require_empty", fixture.statements, close_first=False)
        if not result.accepted:
            raise AssertionError("source proof admitted a live dependency")
        return CallBoundary(result)

    if policy == "defer_destroy":
        return CallBoundary(cleanup("defer_destroy", fixture.statements, close_first=False))

    result = cleanup("recover_busy", fixture.statements, close_first=False)
    if policy == "recover_busy":
        return CallBoundary(result)
    if fixture.state.current_snapshot_allows_close:
        if result.forwards_connection:
            raise AssertionError("current empty snapshot admitted a live dependency")
        return CallBoundary(result)

    # The guard runs after local finalization. Keep those effects and omit close.
    snapshot = fixture.state.snapshot
    stale = snapshot is None or snapshot.version != fixture.state.version
    return CallBoundary(CleanupResult(
        True, "open", result.remaining_statements,
        tuple(call for call in result.calls if call.operation == "finalize"),
    ), "stale_snapshot" if stale else "nonempty_snapshot")
