"""Reference execution for validated MVP semantic graphs and RT-01 CLI input."""

import operator
import re
from collections.abc import Sequence
from dataclasses import dataclass


MIN_I64 = -(1 << 63)
MAX_I64 = (1 << 63) - 1
_ARITHMETIC = {"+": operator.add, "-": operator.sub, "*": operator.mul}
_COMPARISONS = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}
_OPERATIONS = {b"+": "add", b"-": "sub", b"*": "mul", b"/": "div"}
_DIAGNOSTICS = {
    "DivisionByZero": b"division by zero\n",
    "ArithmeticOverflow": b"arithmetic overflow\n",
    "InvalidInput": b"invalid input\n",
}


@dataclass(frozen=True)
class Outcome:
    """An LLMLang function return or an explicit error."""

    value: int | bool | None = None
    error: str | None = None


class _ExecutionError(Exception):
    """Abort evaluation of an enclosing expression with a semantic error."""


def _matches_type(value, kind):
    if kind == "i64":
        return type(value) is int and MIN_I64 <= value <= MAX_I64
    if kind == "bool":
        return type(value) is bool
    raise ValueError(f"unsupported SPG type {kind!r}")


def _execute_binary(symbol, left, right):
    if symbol in _COMPARISONS:
        valid = (
            _matches_type(left, "i64") and _matches_type(right, "i64")
        ) or (
            symbol in {"==", "!="}
            and _matches_type(left, "bool")
            and _matches_type(right, "bool")
        )
        if not valid:
            raise ValueError(f"invalid operands for SPG comparison {symbol!r}")
        return _COMPARISONS[symbol](left, right)
    if not (_matches_type(left, "i64") and _matches_type(right, "i64")):
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
    if not MIN_I64 <= result <= MAX_I64:
        raise _ExecutionError("ArithmeticOverflow")
    return result


def _expression(expr, locals_, functions):
    match expr:
        case ["i64" | "bool" as kind, value] if _matches_type(value, kind):
            return value
        case ["var", name]:
            if name not in locals_:
                raise ValueError(f"unknown SPG variable {name!r}")
            return locals_[name]
        case ["bin", symbol, left, right]:
            lhs = _expression(left, locals_, functions)
            rhs = _expression(right, locals_, functions)
            return _execute_binary(symbol, lhs, rhs)
        case ["call", name, args, pin]:
            callee = functions.get(name)
            if callee is None or callee["impl_hash"] != pin:
                raise ValueError(f"stale or unresolved SPG call binding for {name!r}")
            values = [_expression(arg, locals_, functions) for arg in args]
            return _invoke(callee, values, functions)
        case _:
            raise ValueError(f"unsupported SPG expression {expr!r}")


def _statements(body, locals_, functions):
    for stmt in body:
        match stmt:
            case ["let", name, value]:
                if name in locals_:
                    raise ValueError(f"duplicate SPG variable {name!r}")
                locals_[name] = _expression(value, locals_, functions)
            case ["return", value]:
                return _expression(value, locals_, functions)
            case ["fail", str() as error]:
                raise _ExecutionError(error)
            case ["if", expr, then_body, else_body]:
                condition = _expression(expr, locals_, functions)
                if type(condition) is not bool:
                    raise ValueError("SPG branch condition must be bool")
                branch = then_body if condition else else_body
                result = _statements(branch, locals_.copy(), functions)
                if result is not None:
                    return result
            case _:
                raise ValueError(f"unsupported SPG statement {stmt!r}")
    return None


def _invoke(function, args, functions):
    params = function["params"]
    if len(args) != len(params):
        raise ValueError(f"expected {len(params)} arguments, got {len(args)}")
    locals_ = {}
    for (name, kind), value in zip(params, args, strict=True):
        if not _matches_type(value, kind):
            raise ValueError(f"argument {name!r} must be {kind}")
        locals_[name] = value
    value = _statements(function["body"], locals_, functions)
    if not _matches_type(value, function["result"]):
        raise ValueError("SPG function did not return a value of the declared type")
    return value


def evaluate(spg: dict, name: str, args: Sequence[int | bool]) -> Outcome:
    """Execute a typed function and preserve checked-arithmetic errors."""
    if spg.get("schema") != "llmlang-spg/v1":
        raise ValueError("unsupported SPG schema")
    functions = spg["functions"]
    if name not in functions:
        raise ValueError(f"unknown SPG function {name!r}")
    try:
        return Outcome(value=_invoke(functions[name], args, functions))
    except _ExecutionError as error:
        return Outcome(error=str(error))


def _parse_i64(token):
    if not re.fullmatch(rb"[+-]?[0-9]+", token):
        raise ValueError("invalid integer")
    magnitude = token.lstrip(b"+-").lstrip(b"0") or b"0"
    if len(magnitude) > 19:
        raise ValueError("integer out of range")
    value = int(magnitude)
    if token.startswith(b"-"):
        value = -value
    if not MIN_I64 <= value <= MAX_I64:
        raise ValueError("integer out of range")
    return value


def run_calculator(spg: dict, stdin: bytes) -> tuple[int, bytes, bytes]:
    """Observe one RT-01 calculator record as (exit status, stdout, stderr)."""
    record = stdin.split(b"\n", 1)[0].strip(b" \t\r")
    parts = re.split(rb"[ \t\r]+", record)
    if len(parts) != 3 or parts[1] not in _OPERATIONS:
        return 1, b"", _DIAGNOSTICS["InvalidInput"]
    left, operation, right = parts
    try:
        args = [_parse_i64(left), _parse_i64(right)]
    except ValueError:
        return 1, b"", _DIAGNOSTICS["InvalidInput"]
    result = evaluate(spg, _OPERATIONS[operation], args)
    if result.error is not None:
        if result.error not in _DIAGNOSTICS:
            raise ValueError(f"unrecognized calculator error {result.error!r}")
        return 1, b"", _DIAGNOSTICS[result.error]
    if type(result.value) is not int:
        raise ValueError("calculator operation must return i64")
    return 0, f"{result.value}\n".encode("ascii"), b""
