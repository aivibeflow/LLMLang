"""Connect the COR-13 owned result to a second alias-sensitive call."""

import ast
from dataclasses import dataclass, replace
from typing import Literal, get_args

from rt04_backup_roles import BackupPair, permits
from rt04_owned_call_match import Function, IfFlag, ResultCase, ReturnError, ReturnOwned, WithOwned, observe_call
from rt04_return_disposition import Disposition, TransferTiming


CALLEE = """\
def make(source, destination, wants_value):
    with backup(source, destination) as handle:
        with scratch() as local:
            if wants_value:
                return move(handle)
            else:
                return error()
"""

SOURCE = CALLEE + """\
outcome = make(a, b, wants_value)
source_alias = c
destination_alias = d
propose(outcome, source_alias, destination_alias)
"""

_CALLEE_SHAPE = ast.dump(ast.parse(CALLEE).body[0])
_INPUTS = ("a", "b", "c", "d")
_CLOSE_RESULTS = frozenset(get_args(Disposition))


@dataclass(frozen=True)
class Workload:
    first: BackupPair
    second: BackupPair


@dataclass(frozen=True)
class Inputs:
    identities: tuple[str, str, str, str]
    wants_value: bool
    local_close: Disposition
    handle_close: Disposition


@dataclass(frozen=True)
class Trace:
    result: ResultCase | None
    events: tuple[tuple[str, str, str], ...]
    domain_error: bool
    cleanup_errors: tuple[tuple[str, str], ...]
    second: Literal["not_reached", "refused", "started"]
    reservations: tuple[tuple[str, BackupPair], ...]


def _assignment(node):
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id, node.value
    raise ValueError("expected a local binding")


def _arguments(node, name):
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name
            and not node.keywords and len(node.args) == 3 and all(isinstance(arg, ast.Name) for arg in node.args)):
        return tuple(arg.id for arg in node.args)
    raise ValueError(f"expected {name} with three bound names")


def parse(source: str) -> Workload:
    """Validate the common callee shape and extract its actual caller bindings."""
    try:
        return lower(ast.parse(source).body)
    except SyntaxError as exc:
        raise ValueError("malformed workload source") from exc


def lower(statements: list[ast.stmt]) -> Workload:
    if len(statements) < 3 or ast.dump(statements[0]) != _CALLEE_SHAPE:
        raise ValueError("expected the COR-13 callee")
    name, call = _assignment(statements[1])
    left, right, flag = _arguments(call, "make")
    reserved = set(_INPUTS) | {"make", "propose", "wants_value"}
    if left not in _INPUTS or right not in _INPUTS or flag != "wants_value" or name in reserved:
        raise ValueError("invalid owned call arguments")

    environment = {argument: argument for argument in _INPUTS}
    for node in statements[2:-1]:
        alias, value = _assignment(node)
        if (alias in reserved or alias == name or not isinstance(value, ast.Name)
                or value.id not in environment):
            raise ValueError("invalid caller alias")
        environment[alias] = environment[value.id]

    if not isinstance(statements[-1], ast.Expr):
        raise ValueError("expected a terminal proposal")
    prior, source_name, destination_name = _arguments(statements[-1].value, "propose")
    if prior != name or source_name not in environment or destination_name not in environment:
        raise ValueError("invalid proposed roles or result binding")
    return Workload(BackupPair(left, right), BackupPair(environment[source_name], environment[destination_name]))


def function(timing: TransferTiming) -> Function:
    local = WithOwned("local", _CLOSE_RESULTS, IfFlag(ReturnOwned("handle"), ReturnError()))
    return Function("make", WithOwned("handle", _CLOSE_RESULTS, local), timing)


def call_boundary(workload: Workload, timing: TransferTiming, inputs: Inputs) -> tuple[Trace, BackupPair]:
    """Execute through the first call and resolve the second call's roles."""
    canonical = dict(zip(_INPUTS, inputs.identities, strict=True))
    first = BackupPair(canonical[workload.first.source], canonical[workload.first.destination])
    second = BackupPair(canonical[workload.second.source], canonical[workload.second.destination])
    if not permits((), first):
        return Trace(None, (("check", "handle", "refused"),), False, (), "not_reached", ()), second

    called = observe_call(
        function(timing), flag=inputs.wants_value, local_close=inputs.local_close, handle_close=inputs.handle_close,
    )
    holds = any(obligation.slot == "handle" for obligation in called.case.obligations)
    active = (("handle", first),) if holds else ()
    events = (("check", "handle", "ok"), *called.events)
    return Trace(called.case, events, called.domain_error, called.cleanup_errors, "not_reached", active), second


def propose(trace: Trace, second: BackupPair) -> Trace:
    if trace.result is None:
        return trace
    if permits(tuple(pair for _, pair in trace.reservations), second):
        return replace(trace, second="started", reservations=(*trace.reservations, ("second", second)),
                       events=(*trace.events, ("check", "second", "ok"), ("acquire", "second", "ok")))
    return replace(trace, second="refused", events=(*trace.events, ("check", "second", "refused")))


def execute(workload: Workload, timing: TransferTiming, inputs: Inputs) -> Trace:
    """Compose the existing owned-call evaluator with the backup role guard."""
    return propose(*call_boundary(workload, timing, inputs))
