"""Emit guarded Python for the bounded Scenario 96A integer programs."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "PROTOTYPES" / "LLVM-PRESERVATION-01"))
from integer_fixture import CHECKED_OVERFLOW, DIVISION, SHIFTS, WRAPPING


OPS = {"add": "+", "sub": "-", "mul": "*"}
HEADER = """MASK = 0xffffffff
MIN_SIGNED = -(1 << 31)
MAX_SIGNED = (1 << 31) - 1


def signed(word):
    return (word ^ (1 << 31)) - (1 << 31)


def signed_divmod(left, right):
    quotient, remainder = divmod(left, right)
    if remainder and (left < 0) != (right < 0):
        return quotient + 1, remainder - right
    return quotient, remainder
"""


def instructions(program):
    op = program.operation
    left, right = program.operands
    signed = op.startswith("checked_s")
    if op in WRAPPING:
        return [f"value = {left} {OPS[op[-3:]]} {right}"]
    if op in CHECKED_OVERFLOW:
        bounds = "MIN_SIGNED <= value <= MAX_SIGNED" if signed else "0 <= value <= MASK"
        if signed:
            left, right = f"signed({left})", f"signed({right})"
        return [f"value = {left} {OPS[op[-3:]]} {right}", f"if not {bounds}:", "    return 1"]
    if op in DIVISION:
        lines = [f"if {right} == 0:", "    return 2"]
        if signed:
            left, right = f"signed({left})", f"signed({right})"
            lines += [f"if {left} == MIN_SIGNED and {right} == -1:", "    return 1"]
        divide = "signed_divmod" if signed else "divmod"
        index = 0 if op.endswith("div") else 1
        return lines + [f"value = {divide}({left}, {right})[{index}]"]
    if op in SHIFTS:
        operator = "<<" if op == "checked_shl" else ">>"
        if op == "checked_ashr":
            left = f"signed({left})"
        return [f"if {right} >= 32:", "    return 3", f"value = {left} {operator} {right}"]
    raise ValueError(f"Unsupported operation: {op}")


def lower(programs):
    bodies = []
    for index, program in enumerate(programs):
        statements = "\n".join("        " + line for line in instructions(program))
        bodies.append(f"""
def probe_{index}(a, b, enabled, emit, slot):
    emit(a)
    value = b
    if enabled:
{statements}
    value &= MASK
    emit(value)
    slot[0] = value
    return 0
""".strip())
    registry = ", ".join(f"probe_{index}" for index in range(len(bodies)))
    return "\n\n".join([HEADER.rstrip(), *bodies, f"ENTRIES = ({registry},)"]) + "\n"
