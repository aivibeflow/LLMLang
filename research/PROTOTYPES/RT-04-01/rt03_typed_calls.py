"""Compare strict lexical calls with bindings, local cells, or handled state."""
from __future__ import annotations

from collections.abc import Generator
from copy import deepcopy
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter
from typing import Any

from rt04_model import check_program


class FragmentError(ValueError):
    """The program is invalid or outside this research fragment."""


Value = int | bool | None
Expression = dict[str, Any]
TYPES = {"Int", "Bool", "Unit"}


@dataclass(frozen=True)
class Function:
    params: tuple[tuple[str, str], ...]
    result: str
    body: Expression
    requires_state: bool = False


@dataclass(frozen=True)
class StateWrite:
    before: int
    requested: int
    accepted: bool


@dataclass(frozen=True)
class RejectedWrite:
    requested: int


@dataclass(frozen=True)
class Execution:
    result: Value
    invocations: tuple[str, ...]
    writes: tuple[StateWrite, ...] = ()
    failure: RejectedWrite | None = None


def _value_type(value: Any) -> str:
    if type(value) is bool:
        return "Bool"
    if type(value) is int:
        return "Int"
    if value is None:
        return "Unit"
    raise FragmentError("only Int, Bool and Unit values are supported")


def _expect(actual: str, expected: str, where: str) -> None:
    if actual != expected:
        raise FragmentError(f"{where}: expected {expected}, got {actual}")


def project_program(functions: dict[str, Function], semantics: str) -> dict[str, Any]:
    """Validate bodies and derive RT-04 call declarations from their actual call sites.

    For D, this pass also checks state requirements. The RT-04 projection for
    D contains signatures and the call graph, since the existing checker lacks
    a handler-aware effect bound.
    """
    if semantics not in {"A", "B", "D"}:
        raise FragmentError("typed call semantics must be A, B, or D")
    if not functions:
        raise FragmentError("at least one function is required")
    for name, function in functions.items():
        if not isinstance(name, str) or not name:
            raise FragmentError("function names must be non-empty strings")
        if (not isinstance(function, Function) or not isinstance(function.result, str)
                or function.result not in TYPES):
            raise FragmentError(f"{name}: an explicit supported signature is required")
        if not isinstance(function.params, tuple) or any(
            not isinstance(pair, tuple) or len(pair) != 2
            or not isinstance(pair[0], str) or not pair[0]
            or not isinstance(pair[1], str) or pair[1] not in TYPES
            for pair in function.params
        ):
            raise FragmentError(f"{name}: parameters must have names and supported types")
        params = dict(function.params)
        if len(params) != len(function.params):
            raise FragmentError(f"{name}: parameter names must be unique")
        if type(function.requires_state) is not bool or (function.requires_state and semantics != "D"):
            raise FragmentError(f"{name}: requires_state is a boolean effect declaration for D")

    def project_body(name: str, function: Function) -> dict[str, Any]:
        sites = []

        def infer(expr: Expression, scope: dict[str, tuple[str, bool]], state_available: bool) -> str:
            if not isinstance(expr, dict) or len(expr) != 1:
                raise FragmentError(f"{name}: expected one expression form")

            def child(expression: Expression) -> str:
                return infer(expression, scope, state_available)

            match expr:
                case {"literal": value}:
                    return _value_type(value)
                case {"var": str(binding)} if binding in scope:
                    return scope[binding][0]
                case {"var": binding}:
                    raise FragmentError(f"{name}: unknown variable {binding!r}")
                case {"add": [left, right]}:
                    for operand in (left, right):
                        _expect(child(operand), "Int", f"{name}: add")
                    return "Int"
                case {"if": [condition, then, otherwise]}:
                    _expect(child(condition), "Bool", f"{name}: if condition")
                    left = child(then)
                    _expect(child(otherwise), left, f"{name}: if branch")
                    return left
                case {"sequence": list(items)} if items:
                    for item in items:
                        result = child(item)
                    return result
                case {"call": [str(target), list(args)]}:
                    if target not in functions:
                        raise FragmentError(f"{name}: unknown callee {target!r}")
                    arg_types = [child(arg) for arg in args]
                    if functions[target].requires_state and not state_available:
                        raise FragmentError(f"{name}: call to {target!r} requires state")
                    sites.append({"target": target, "args": arg_types})
                    return functions[target].result
                case {"let": [str(binding), initializer, body]} if binding:
                    return infer(body, {**scope, binding: (child(initializer), False)}, state_available)
                case {"local": [str(binding), initializer, body]} if binding and semantics == "B":
                    return infer(body, {**scope, binding: (child(initializer), True)}, state_available)
                case {"set": [str(binding), value]} if semantics == "B":
                    if binding not in scope or not scope[binding][1]:
                        raise FragmentError(f"{name}: assignment requires a mutable local {binding!r}")
                    _expect(child(value), scope[binding][0], f"{name}: assignment to {binding}")
                    return "Unit"
                case {"handle_state": [initializer, bool(), bool(), body]} if semantics == "D":
                    _expect(child(initializer), "Int", f"{name}: state initializer")
                    return infer(body, scope, True)
                case {"state_get": None} if state_available:
                    return "Int"
                case {"state_put": value} if state_available:
                    _expect(child(value), "Int", f"{name}: state write")
                    return "Unit"
                case {"state_get": None} | {"state_put": _} if semantics == "D":
                    raise FragmentError(f"{name}: operation requires state")
                case _:
                    raise FragmentError(f"{name}: unsupported or malformed {next(iter(expr))!r} in {semantics}")

        scope = {param: (sort, False) for param, sort in function.params}
        _expect(infer(function.body, scope, function.requires_state), function.result, f"{name}: return")
        declaration = {
            "params": dict(function.params),
            "result": function.result,
            "calls": list(dict.fromkeys(site["target"] for site in sites)),
            "call_sites": sites,
        }
        if semantics != "D":
            declaration["effect_bound"] = []
        return declaration

    declarations = {name: project_body(name, fn) for name, fn in functions.items()}
    calls = {name: decl["calls"] for name, decl in declarations.items()}
    try:
        TopologicalSorter(calls).prepare()
    except CycleError as exc:
        raise FragmentError("recursive calls are outside this fragment") from exc
    return {"functions": declarations, "call_graph_complete": list(declarations)}


@dataclass
class _Cell:
    value: Value


@dataclass(frozen=True)
class _StateRequest:
    value: int | None


class _WriteFailure(Exception):
    def __init__(self, requested: int):
        self.requested = requested


Computation = Generator[_StateRequest, Value, Value]


def _handle_state(
    computation: Computation,
    state: int,
    observe_writes: bool,
    reject_negative: bool,
    writes: list[StateWrite],
) -> Value:
    try:
        request = next(computation)
        while True:
            value = request.value
            if value is None:
                request = computation.send(state)
                continue
            accepted = not reject_negative or value >= 0
            if observe_writes:
                writes.append(StateWrite(state, value, accepted))
            if not accepted:
                computation.close()
                raise _WriteFailure(value)
            state = value
            request = computation.send(None)
    except StopIteration as completed:
        return completed.value


def run_program(
    functions: dict[str, Function],
    entry: str,
    arguments: tuple[Value, ...],
    semantics: str,
    *,
    checker: str,
) -> Execution:
    """Run only programs accepted by the body checks and the chosen RT-04 checker."""
    functions = deepcopy(functions)
    checked = check_program(project_program(functions, semantics), checker)
    if checked.status != "ACCEPTED":
        raise FragmentError(f"RT-04 {checked.status}: {', '.join(sorted(checked.codes()))}")
    if entry not in functions:
        raise FragmentError(f"unknown entry {entry!r}")
    if functions[entry].requires_state:
        raise FragmentError(f"{entry}: entry requires a state handler")
    if len(arguments) != len(functions[entry].params):
        raise FragmentError(f"{entry}: entry argument count does not match signature")
    for (param, sort), value in zip(functions[entry].params, arguments):
        _expect(_value_type(value), sort, f"{entry}: argument {param}")

    invocations: list[str] = []
    writes: list[StateWrite] = []

    def invoke(name: str, args: tuple[Value, ...]) -> Computation:
        function = functions[name]
        invocations.append(name)
        scope = {param: value for (param, _), value in zip(function.params, args)}
        return (yield from execute(function.body, scope))

    def execute(expr: Expression, scope: dict[str, Value | _Cell]) -> Computation:
        match expr:
            case {"literal": value}:
                return value
            case {"var": binding}:
                bound = scope[binding]
                return bound.value if isinstance(bound, _Cell) else bound
            case {"add": [left, right]}:
                left_value = yield from execute(left, scope)
                right_value = yield from execute(right, scope)
                return left_value + right_value
            case {"if": [condition, then, otherwise]}:
                condition_value = yield from execute(condition, scope)
                return (yield from execute(then if condition_value else otherwise, scope))
            case {"sequence": items}:
                for item in items:
                    result = yield from execute(item, scope)
                return result
            case {"call": [target, args]}:
                values = []
                for arg in args:
                    values.append((yield from execute(arg, scope)))
                return (yield from invoke(target, tuple(values)))
            case {"let": [binding, initializer, body]}:
                value = yield from execute(initializer, scope)
                return (yield from execute(body, {**scope, binding: value}))
            case {"local": [binding, initializer, body]}:
                value = yield from execute(initializer, scope)
                return (yield from execute(body, {**scope, binding: _Cell(value)}))
            case {"set": [binding, value]}:
                cell = scope[binding]
                assert isinstance(cell, _Cell)
                cell.value = yield from execute(value, scope)
                return None
            case {"handle_state": [initializer, observe_writes, reject_negative, body]}:
                initial = yield from execute(initializer, scope)
                return _handle_state(execute(body, scope), initial, observe_writes, reject_negative, writes)
            case {"state_get": None}:
                return (yield _StateRequest(None))
            case {"state_put": expression}:
                value = yield from execute(expression, scope)
                yield _StateRequest(value)
                return None
            case _:
                raise AssertionError("validated expression has no execution rule")

    try:
        next(invoke(entry, arguments))
    except StopIteration as completed:
        return Execution(completed.value, tuple(invocations), tuple(writes))
    except _WriteFailure as failed:
        return Execution(None, tuple(invocations), tuple(writes), RejectedWrite(failed.requested))
    raise AssertionError("validated entry emitted an unhandled state request")
