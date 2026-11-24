"""Lower the checked Scenario 96A integer fixture to C++20 source."""

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "PROTOTYPES" / "LLVM-PRESERVATION-01"))
from integer_fixture import CHECKED_OVERFLOW, DIVISION, SHIFTS, WRAPPING


HEADER = """#include <cstdint>

using u32 = std::uint32_t;
using i64 = std::int64_t;
using u64 = std::uint64_t;
using Emit = void (*)(u32);

[[maybe_unused]] static constexpr i64 signed_value(u32 bits) noexcept {
    return bits <= 0x7fff'ffffu ? static_cast<i64>(bits)
                               : static_cast<i64>(bits) - 0x1'0000'0000LL;
}
"""
SYMBOLS = {"add": "+", "sub": "-", "mul": "*"}


def operation(program):
    op = program.operation
    left, right = program.operands
    if op in WRAPPING:
        return [f"value = {left} {SYMBOLS[op[-3:]]} {right};"]
    if op in CHECKED_OVERFLOW:
        symbol = SYMBOLS[op[-3:]]
        if op.startswith("checked_s"):
            return [
                f"const i64 wide = signed_value({left}) {symbol} signed_value({right});",
                "if (wide < -2147483648LL || wide > 2147483647LL) return 1;",
                "value = static_cast<u32>(wide);",
            ]
        if symbol == "-":
            if left == right:
                return ["value = 0;"]
            return [f"if ({left} < {right}) return 1;", f"value = {left} - {right};"]
        return [
            f"const u64 wide = static_cast<u64>({left}) {symbol} static_cast<u64>({right});",
            "if (wide > 0xffff'ffffULL) return 1;",
            "value = static_cast<u32>(wide);",
        ]
    if op in DIVISION:
        symbol = "/" if op.endswith("div") else "%"
        lines = [f"if ({right} == 0u) return 2;"]
        if op.startswith("checked_s"):
            if left != right:
                lines.append(f"if ({left} == 0x8000'0000u && {right} == 0xffff'ffffu) return 1;")
            lines.append(f"value = static_cast<u32>(signed_value({left}) {symbol} signed_value({right}));")
        else:
            lines.append(f"value = {left} {symbol} {right};")
        return lines
    if op in SHIFTS:
        expressions = {"checked_shl": f"{left} << {right}", "checked_lshr": f"{left} >> {right}",
                       "checked_ashr": f"static_cast<u32>(signed_value({left}) >> {right})"}
        return [f"if ({right} >= 32u) return 3;", f"value = {expressions[op]};"]
    raise ValueError(f"Unsupported integer operation: {op}")


def lower(programs):
    definitions = [HEADER.rstrip()]
    for index, program in enumerate(programs):
        statements = "\n".join("        " + line for line in operation(program))
        definitions.append(f'''extern "C" u32 probe_{index}(u32 a, u32 b, u32 enabled, Emit emit, u32 *out) noexcept {{
    emit(a);
    u32 value = b;
    if (enabled != 0u) {{
{statements}
    }}
    emit(value);
    *out = value;
    return 0;
}}''')
    return "\n\n".join(definitions) + "\n"
