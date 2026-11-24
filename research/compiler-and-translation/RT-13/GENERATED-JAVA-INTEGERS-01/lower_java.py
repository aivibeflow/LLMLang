"""Lower the shared checked bounded integer Program to Java 21."""

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "PROTOTYPES" / "LLVM-PRESERVATION-01"))
from integer_fixture import CHECKED_OVERFLOW, DIVISION, SHIFTS, WRAPPING


ARITHMETIC = {"add": "+", "sub": "-", "mul": "*"}
SHIFT = {"checked_shl": "<<", "checked_ashr": ">>", "checked_lshr": ">>>"}
HERE = Path(__file__).resolve().parent


def operation(program):
    op = program.operation
    left, right = program.operands
    if op in WRAPPING:
        return [f"value = {left} {ARITHMETIC[op[-3:]]} {right};"]
    if op in CHECKED_OVERFLOW:
        symbol = ARITHMETIC[op[-3:]]
        if op.startswith("checked_s"):
            return [f"long wide = (long) {left} {symbol} (long) {right};",
                    "if (wide < Integer.MIN_VALUE || wide > Integer.MAX_VALUE) return 1;",
                    "value = (int) wide;"]
        lines = [f"long x = Integer.toUnsignedLong({left});", f"long y = Integer.toUnsignedLong({right});"]
        if symbol == "*":
            lines.extend(("if (x != 0 && y > 0xffff_ffffL / x) return 1;", "value = (int) (x * y);"))
        else:
            lines.extend((f"long wide = x {symbol} y;", "if (wide < 0 || wide > 0xffff_ffffL) return 1;",
                          "value = (int) wide;"))
        return lines
    if op in DIVISION:
        div = op.endswith("div")
        lines = [f"if ({right} == 0) return 2;"]
        if op.startswith("checked_s"):
            lines += [f"if ({left} == Integer.MIN_VALUE && {right} == -1) return 1;",
                      f"value = {left} {'/' if div else '%'} {right};"]
        else:
            method = "divideUnsigned" if div else "remainderUnsigned"
            lines.append(f"value = Integer.{method}({left}, {right});")
        return lines
    if op in SHIFTS:
        return [f"if (Integer.compareUnsigned({right}, 32) >= 0) return 3;",
                f"value = {left} {SHIFT[op]} {right};"]
    raise ValueError(f"Unsupported operation: {op}")


def lower(programs):
    bodies = []
    for index, program in enumerate(programs):
        statements = "\n".join("            " + line for line in operation(program))
        bodies.append(f"""    static int probe{index}(int a, int b, int enabled, Trace trace) {{
        trace.emit(a);
        int value = b;
        if (enabled != 0) {{
{statements}
        }}
        trace.emit(value);
        trace.slot = value;
        return 0;
    }}""")
    selectors = [f"            case {index} -> probe{index}(a, b, enabled, trace);"
                 for index in range(len(programs))]
    return (HERE / "host.java.in").read_text(encoding="utf-8").replace(
        "    // @GENERATED_PROBES@", "\n\n".join(bodies)
    ).replace("            // @GENERATED_REGISTRY@", "\n".join(selectors))
