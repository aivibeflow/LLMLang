"""Type-check caller match arms before an alias-sensitive proposal."""

import ast
from dataclasses import dataclass, replace
from typing import get_args

from rt04_owned_call_match import Obligation, ResultCase, infer_result_cases
from rt04_return_disposition import Disposition, TransferTiming
from rt04_shared_owned_workload import Inputs, SOURCE, Trace, Workload, call_boundary, function, lower, propose


_MATCH = """\
match outcome:
    case "success":
        preserve()
    case "error_with_handle":
        release_first()
    case "error_reconcile":
        preserve()
    case "error_without_handle":
        preserve()
"""
RECOVER_SOURCE = SOURCE.replace("propose(outcome,", _MATCH + "propose(outcome,")
PRESERVE_SOURCE = RECOVER_SOURCE.replace("release_first()", "preserve()")


@dataclass(frozen=True)
class Caller:
    workload: Workload
    timing: TransferTiming
    actions: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class CallerTrace:
    """Keep the original callee result and the obligations after caller actions."""

    trace: Trace
    forwarded: frozenset[Obligation]


def _group(case: ResultCase) -> str:
    if case.tag == "OkWithValue":
        return "success"
    handle = next((item for item in case.obligations if item.slot == "handle"), None)
    if handle is None:
        return "error_without_handle"
    return "error_reconcile" if handle.kind == "reconcile" else "error_with_handle"


def _arm(node):
    if (not isinstance(node.pattern, ast.MatchValue) or not isinstance(node.pattern.value, ast.Constant)
            or not isinstance(node.pattern.value.value, str) or node.guard is not None or len(node.body) != 1):
        raise ValueError("expected a single unguarded result arm")
    statement = node.body[0]
    if (not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call)
            or not isinstance(statement.value.func, ast.Name) or statement.value.args or statement.value.keywords
            or statement.value.func.id not in ("preserve", "release_first")):
        raise ValueError("unsupported caller action")
    return node.pattern.value.value, statement.value.func.id


def compile_caller(source: str, timing: TransferTiming) -> Caller:
    try:
        statements = ast.parse(source).body
    except SyntaxError as exc:
        raise ValueError("malformed caller source") from exc
    if len(statements) < 4 or not isinstance(statements[-2], ast.Match):
        raise ValueError("expected result match before the proposal")
    match = statements[-2]
    workload = lower(statements[:-2] + statements[-1:])
    if not isinstance(match.subject, ast.Name) or match.subject.id != statements[1].targets[0].id:
        raise ValueError("match must inspect the callee result")

    actions = dict(_arm(node) for node in match.cases)
    shapes = infer_result_cases(function(timing))
    if len(actions) != len(match.cases) or actions.keys() != {_group(case) for case in shapes}:
        raise ValueError("match requires one arm for each inferred result group")
    for case in shapes:
        usable = any(item.slot == "handle" and item.kind in ("owned", "retained") for item in case.obligations)
        if actions[_group(case)] == "release_first" and not usable:
            raise ValueError("release_first requires a usable handle on every route in its arm")
    return Caller(workload, timing, tuple(actions.items()))


def execute(caller: Caller, inputs: Inputs, disposition: Disposition) -> CallerTrace:
    trace, second = call_boundary(caller.workload, caller.timing, inputs)
    if trace.result is None:
        return CallerTrace(trace, frozenset())

    group = _group(trace.result)
    action = dict(caller.actions)[group]
    trace = replace(trace, events=(*trace.events, ("match", group, action)))
    forwarded = trace.result.obligations
    if action == "release_first":
        if disposition not in get_args(Disposition):
            raise ValueError("unsupported caller release disposition")
        remaining = {item for item in forwarded if item.slot != "handle"}
        if disposition == "retained_error":
            remaining.add(Obligation("handle", "retained"))
        if disposition == "indeterminate":
            remaining.add(Obligation("handle", "reconcile"))
        forwarded = frozenset(remaining)
        errors = trace.cleanup_errors if disposition == "ok" else (*trace.cleanup_errors, ("caller_handle", disposition))
        reservations = trace.reservations
        if disposition in ("ok", "consumed_error"):
            reservations = tuple(entry for entry in reservations if entry[0] != "handle")
        trace = replace(trace, events=(*trace.events, ("release", "caller_handle", disposition)),
                        cleanup_errors=errors, reservations=reservations)
    return CallerTrace(propose(trace, second), forwarded)
