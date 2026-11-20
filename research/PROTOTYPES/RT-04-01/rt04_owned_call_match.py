"""Infer the obligations of a named owned-resource call from a small AST."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, get_args

from rt04_return_disposition import Disposition, TransferTiming, run_return_disposition


@dataclass(frozen=True)
class ReturnOwned:
    binding: str


@dataclass(frozen=True)
class ReturnError:
    """Return the fixture's domain error before moving a resource."""


@dataclass(frozen=True)
class IfFlag:
    when_true: ReturnOwned | ReturnError
    when_false: ReturnOwned | ReturnError


@dataclass(frozen=True)
class WithOwned:
    binding: str
    close_results: frozenset[Disposition]
    body: WithOwned | IfFlag | ReturnOwned | ReturnError


@dataclass(frozen=True)
class Function:
    name: str
    body: WithOwned
    transfer: TransferTiming


@dataclass(frozen=True)
class Obligation:
    slot: Literal["handle", "local"]
    kind: Literal["owned", "retained", "reconcile"]


@dataclass(frozen=True)
class ResultCase:
    tag: str
    obligations: frozenset[Obligation] = frozenset()


@dataclass(frozen=True)
class MatchArm:
    pattern: ResultCase
    moves: tuple[str, ...]


@dataclass(frozen=True)
class MatchCall:
    callee: str
    arms: tuple[MatchArm, ...]
    output: Literal["plain_result", "tagged_outcome"]


@dataclass(frozen=True)
class MatchIssue:
    code: str
    case: ResultCase


@dataclass(frozen=True)
class CallTrace:
    case: ResultCase
    events: tuple[tuple[str, str, str], ...]
    domain_error: bool
    cleanup_errors: tuple[tuple[str, str], ...]


def _scopes(function: Function) -> tuple[WithOwned, WithOwned]:
    if not isinstance(function.name, str) or not function.name:
        raise ValueError("the function needs a name")
    if function.transfer not in get_args(TransferTiming):
        raise ValueError("unsupported transfer timing")
    outer = function.body
    if not isinstance(outer, WithOwned) or not isinstance(outer.body, WithOwned):
        raise ValueError("expected two nested owned scopes")
    inner = outer.body
    if any(not isinstance(scope.binding, str) or not scope.binding for scope in (outer, inner)):
        raise ValueError("each scope needs a binding name")
    if outer.binding == inner.binding:
        raise ValueError("owned scope bindings must be distinct")
    for scope in (outer, inner):
        if (not isinstance(scope.close_results, frozenset) or not scope.close_results
                or not scope.close_results.issubset(get_args(Disposition))):
            raise ValueError(f"invalid close contract for {scope.binding}")

    body = inner.body
    exits = (body.when_true, body.when_false) if isinstance(body, IfFlag) else (body,)
    for exit_ in exits:
        if not isinstance(exit_, (ReturnOwned, ReturnError)):
            raise ValueError("unsupported function exit")
        if isinstance(exit_, ReturnOwned) and exit_.binding != outer.binding:
            raise ValueError("this fragment can move only the outer binding")
    return outer, inner


def infer_result_cases(function: Function) -> frozenset[ResultCase]:
    """Derive alternatives using the path structure and declared close contracts."""
    outer, inner = _scopes(function)
    body = inner.body
    exits = (body.when_true, body.when_false) if isinstance(body, IfFlag) else (body,)
    cases = set()
    for exit_ in exits:
        for local in inner.close_results:
            moves_value = isinstance(exit_, ReturnOwned) and (
                function.transfer == "before_cleanup" or local == "ok"
            )
            pending_results = ("ok",) if moves_value else outer.close_results
            for pending in pending_results:
                cleanup_failed = local != "ok" or pending != "ok"
                if isinstance(exit_, ReturnError):
                    tag = "ErrWithCleanupErrors" if cleanup_failed else "Err"
                elif moves_value:
                    tag = "CleanupFailedWithValue" if cleanup_failed else "OkWithValue"
                else:
                    tag = "StagedCleanupFailedWithoutValue"

                obligations = {Obligation("handle", "owned")} if moves_value else set()
                for slot, disposition in (("local", local), ("handle", pending)):
                    if disposition == "retained_error":
                        obligations.add(Obligation(slot, "retained"))
                    elif disposition == "indeterminate":
                        obligations.add(Obligation(slot, "reconcile"))
                cases.add(ResultCase(tag, frozenset(obligations)))
    return frozenset(cases)


def check_match(function: Function, call: MatchCall) -> frozenset[MatchIssue]:
    """Check an exact match whose arms forward the result and its obligations."""
    if call.callee != function.name:
        raise ValueError("unresolved call")
    return check_result_arms(infer_result_cases(function), call.arms, output=call.output)


def check_result_arms(
    cases: frozenset[ResultCase], arms: tuple[MatchArm, ...], *,
    output: Literal["plain_result", "tagged_outcome"],
) -> frozenset[MatchIssue]:
    """Check exhaustive forwarding against a finite set of result shapes."""
    if output not in ("plain_result", "tagged_outcome"):
        raise ValueError("unsupported output type")
    seen = set()
    issues = set()
    for arm in arms:
        case = arm.pattern
        if case in seen:
            issues.add(MatchIssue("DUPLICATE_ARM", case))
        seen.add(case)
        if case not in cases:
            issues.add(MatchIssue("UNEXPECTED_ARM", case))
            continue
        expected = {obligation.slot for obligation in case.obligations}
        moved = set(arm.moves)
        if len(moved) != len(arm.moves):
            issues.add(MatchIssue("DUPLICATE_MOVE", case))
        if moved - expected:
            issues.add(MatchIssue("MOVE_WITHOUT_OBLIGATION", case))
        if expected - moved:
            issues.add(MatchIssue("MISSING_MOVE", case))
        if output == "plain_result" and case.tag != "OkWithValue" and expected:
            issues.add(MatchIssue("ERROR_CANNOT_CARRY_OBLIGATIONS", case))
    issues.update(MatchIssue("MISSING_ARM", case) for case in cases - seen)
    return frozenset(issues)


def observe_call(
    function: Function, *, flag: bool, local_close: Disposition, handle_close: Disposition,
) -> CallTrace:
    """Run the existing COR-13 disposition semantics for one concrete input."""
    outer, inner = _scopes(function)
    if type(flag) is not bool:
        raise ValueError("expected Boolean branch input")
    if local_close not in inner.close_results or handle_close not in outer.close_results:
        raise ValueError("close result outside the declared contract")
    body = inner.body
    if isinstance(body, IfFlag):
        body = body.when_true if flag else body.when_false
    domain_error = isinstance(body, ReturnError)
    runtime = run_return_disposition(
        body="domain_error_before_transfer" if domain_error else "success",
        transfer_timing=function.transfer,
        local_disposition=local_close,
        pending_handle_disposition=handle_close,
    )
    names = {"handle": outer.binding, "local": inner.binding}
    kinds = {
        "caller_owned": "owned", "live_cleanup_debt": "retained", "ownership_unknown": "reconcile",
    }
    obligations = frozenset(
        Obligation(resource, kinds[state]) for resource, state in runtime.resource_states if state in kinds
    )
    close_events = tuple((action, names[resource], result) for action, resource, result in runtime.events)
    events = (("acquire", outer.binding, "ok"), ("acquire", inner.binding, "ok")) + close_events
    errors = tuple((name, result) for action, name, result in close_events if action == "release" and result != "ok")
    return CallTrace(ResultCase(runtime.tag, obligations), events, domain_error, errors)


def execute_match(
    function: Function, call: MatchCall, *, flag: bool, local_close: Disposition, handle_close: Disposition,
) -> CallTrace:
    """Execute one accepted call and move each matched obligation upstream."""
    if issues := check_match(function, call):
        raise ValueError(f"invalid ownership match: {sorted({issue.code for issue in issues})}")
    trace = observe_call(function, flag=flag, local_close=local_close, handle_close=handle_close)
    arm = next((arm for arm in call.arms if arm.pattern == trace.case), None)
    if arm is None:
        raise AssertionError("observed case falls outside the inferred result type")
    obligations = {obligation.slot: obligation.kind for obligation in trace.case.obligations}
    moves = tuple(("forward", slot, obligations[slot]) for slot in arm.moves)
    output_case = trace.case
    if call.output == "plain_result":
        tag = "Ok" if trace.case.tag == "OkWithValue" else "Err"
        output_case = ResultCase(tag, trace.case.obligations)
    return CallTrace(output_case, trace.events + moves, trace.domain_error, trace.cleanup_errors)
