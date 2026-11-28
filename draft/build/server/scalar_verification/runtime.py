"""Reference execution of scalar semantic graphs for counterexample replay."""

import operator
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .frontend import INTEGER_TYPES

_ARITHMETIC = {"+": operator.add, "-": operator.sub, "*": operator.mul}
_COMPARISONS = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


@dataclass(frozen=True)
class Outcome:
    """An LLMLang function return or an explicit error."""

    value: int | bool | None = None
    error: str | None = None


class _ExecutionError(Exception):
    """Abort evaluation of an enclosing expression with a semantic error."""


def _matches_type(value, kind):
    if kind in INTEGER_TYPES:
        low, high = INTEGER_TYPES[kind]
        return type(value) is int and low <= value <= high
    if kind == "bool":
        return type(value) is bool
    raise ValueError(f"unsupported SPG type {kind!r}")


def _execute_binary(symbol, left, right, kind):
    if symbol in _COMPARISONS:
        valid = (
            kind in INTEGER_TYPES and _matches_type(left, kind) and _matches_type(right, kind)
        ) or (
            symbol in {"==", "!="}
            and _matches_type(left, "bool")
            and _matches_type(right, "bool")
        )
        if not valid:
            raise ValueError(f"invalid operands for SPG comparison {symbol!r}")
        return _COMPARISONS[symbol](left, right)
    if not (kind in INTEGER_TYPES and _matches_type(left, kind) and _matches_type(right, kind)):
        raise ValueError(f"invalid operands for SPG arithmetic {symbol!r}")
    if symbol == "/":
        if right == 0:
            raise _ExecutionError("DivisionByZero")
        magnitude = abs(left) // abs(right)
        result = -magnitude if (left < 0) != (right < 0) else magnitude
    elif symbol in _ARITHMETIC:
        result = _ARITHMETIC[symbol](left, right)
    else:
        raise ValueError(f"unsupported SPG binary operator {symbol!r}")
    if not _matches_type(result, kind):
        raise _ExecutionError("ArithmeticOverflow")
    return result


def _expression(expr, locals_, functions, caller, observe_call):
    match expr:
        case ["i64" | "u64" | "bool" as kind, value] if _matches_type(value, kind):
            return value, kind
        case ["var", name]:
            if name not in locals_:
                raise ValueError(f"unknown SPG variable {name!r}")
            return locals_[name]
        case ["bin", symbol, left, right]:
            lhs, left_kind = _expression(left, locals_, functions, caller, observe_call)
            rhs, right_kind = _expression(right, locals_, functions, caller, observe_call)
            if left_kind != right_kind:
                raise ValueError("inconsistent operand types")
            result = _execute_binary(symbol, lhs, rhs, left_kind)
            return result, "bool" if symbol in _COMPARISONS else left_kind
        case ["call", name, args, pin]:
            callee = functions.get(name)
            if callee is None or callee["impl_hash"] != pin:
                raise ValueError(f"stale or unresolved SPG call binding for {name!r}")
            values = tuple(_expression(arg, locals_, functions, caller, observe_call)[0] for arg in args)
            if observe_call is not None:
                observe_call(caller, name, values)
            return _invoke(name, values, functions, observe_call), callee["result"]
        case _:
            raise ValueError(f"unsupported SPG expression {expr!r}")


def _statements(body, locals_, functions, caller, observe_call):
    for stmt in body:
        match stmt:
            case ["let", name, value]:
                if name in locals_:
                    raise ValueError(f"duplicate SPG variable {name!r}")
                locals_[name] = _expression(value, locals_, functions, caller, observe_call)
            case ["return", value]:
                return _expression(value, locals_, functions, caller, observe_call)
            case ["fail", str() as error]:
                raise _ExecutionError(error)
            case ["if", expr, then_body, else_body]:
                condition, _ = _expression(expr, locals_, functions, caller, observe_call)
                if type(condition) is not bool:
                    raise ValueError("SPG branch condition must be bool")
                branch = then_body if condition else else_body
                result = _statements(branch, locals_.copy(), functions, caller, observe_call)
                if result is not None:
                    return result
            case _:
                raise ValueError(f"unsupported SPG statement {stmt!r}")
    return None


def _invoke(name, args, functions, observe_call):
    function = functions[name]
    params = function["params"]
    if len(args) != len(params):
        raise ValueError(f"expected {len(params)} arguments, got {len(args)}")
    locals_ = {}
    for (parameter, kind), value in zip(params, args, strict=True):
        if not _matches_type(value, kind):
            raise ValueError(f"argument {parameter!r} must be {kind}")
        locals_[parameter] = value, kind
    result = _statements(function["body"], locals_, functions, name, observe_call)
    if result is None:
        raise ValueError("SPG function did not return")
    value, kind = result
    if kind != function["result"] or not _matches_type(value, kind):
        raise ValueError("SPG function did not return a value of the declared type")
    return value


def evaluate(
    spg: dict,
    name: str,
    args: Sequence[int | bool],
    *,
    observe_call: Callable[[str, str, tuple[int | bool, ...]], None] | None = None,
) -> Outcome:
    """Execute a typed function and optionally report exact calls and arguments."""
    if spg.get("schema") != "llmlang-spg/v1":
        raise ValueError("unsupported SPG schema")
    functions = spg["functions"]
    if name not in functions:
        raise ValueError(f"unknown SPG function {name!r}")
    try:
        return Outcome(value=_invoke(name, args, functions, observe_call))
    except _ExecutionError as error:
        return Outcome(error=str(error))
