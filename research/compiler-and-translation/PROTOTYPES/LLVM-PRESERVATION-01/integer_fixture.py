"""Bounded source contract and reference observations for Scenario 96A."""

import ast
from dataclasses import dataclass


SOURCE = """\
def probe(a, b, enabled):
    emit(a)
    if enabled:
        value = operation(a, b)
    else:
        value = b
    emit(value)
    return value
"""
_SHAPE = ast.dump(ast.parse(SOURCE))
WRAPPING = ("wrap_add", "wrap_sub", "wrap_mul")
CHECKED_OVERFLOW = tuple(f"checked_{sign}{op}" for sign in ("s", "u") for op in ("add", "sub", "mul"))
DIVISION = ("checked_sdiv", "checked_srem", "checked_udiv", "checked_urem")
SHIFTS = ("checked_shl", "checked_ashr", "checked_lshr")
OPERATIONS = WRAPPING + CHECKED_OVERFLOW + DIVISION + SHIFTS
_LIMIT = 2**32
_SIGNED_MIN = -(2**31)


@dataclass(frozen=True)
class Program:
    operation: str
    operands: tuple[str, str]


@dataclass(frozen=True)
class Observation:
    status: str
    value: int | None
    events: tuple[int, ...]


def compile_source(source: str) -> Program:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError("malformed integer fixture") from exc
    match tree.body:
        case [ast.FunctionDef(body=[_, ast.If(body=[ast.Assign(value=ast.Call(
            func=ast.Name(id=operation), args=[ast.Name(id=left), ast.Name(id=right)],
        ) as call)]), _, _])]:
            if operation not in OPERATIONS or left not in ("a", "b") or right not in ("a", "b"):
                raise ValueError("unsupported integer operation or operand")
            call.func.id = "operation"
            for node, name in zip(call.args, ("a", "b"), strict=True):
                node.id = name
            if ast.dump(tree) == _SHAPE:
                return Program(operation, (left, right))
    raise ValueError("expected bounded integer fixture")


def _signed(value: int) -> int:
    return value if value < 2**31 else value - _LIMIT


def _arithmetic(operation: str, x: int, y: int) -> int:
    match operation[-3:]:
        case "add":
            return x + y
        case "sub":
            return x - y
        case "mul":
            return x * y
    raise ValueError(operation)


def evaluate(program: Program, a: int, b: int, enabled: bool) -> Observation:
    if not enabled:
        return Observation("ok", b, (a, b))
    values = {"a": a, "b": b}
    x, y = (values[name] for name in program.operands)
    op = program.operation
    if op in WRAPPING:
        result = _arithmetic(op, x, y)
    elif op in CHECKED_OVERFLOW:
        if op.startswith("checked_s"):
            result = _arithmetic(op, _signed(x), _signed(y))
            low, high = _SIGNED_MIN, -_SIGNED_MIN
        else:
            result = _arithmetic(op, x, y)
            low, high = 0, _LIMIT
        if result < low or result >= high:
            return Observation("overflow", None, (a,))
    elif op in DIVISION:
        if y == 0:
            return Observation("zero_divisor", None, (a,))
        if op.startswith("checked_s"):
            x, y = _signed(x), _signed(y)
            if x == _SIGNED_MIN and y == -1:
                return Observation("overflow", None, (a,))
        quotient = abs(x) // abs(y)
        if (x < 0) != (y < 0):
            quotient = -quotient
        result = quotient if op.endswith("div") else x - quotient * y
    else:
        if y >= 32:
            return Observation("shift_count", None, (a,))
        match op:
            case "checked_shl":
                result = x << y
            case "checked_ashr":
                result = _signed(x) >> y
            case "checked_lshr":
                result = x >> y
            case _:
                raise ValueError(op)
    bits = result % _LIMIT
    return Observation("ok", bits, (a, bits))
