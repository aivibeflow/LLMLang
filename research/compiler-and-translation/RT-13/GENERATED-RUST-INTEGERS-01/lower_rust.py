"""Lower the bounded Scenario 96A integer Program to Rust source."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "PROTOTYPES" / "LLVM-PRESERVATION-01"))
from integer_fixture import CHECKED_OVERFLOW, DIVISION, SHIFTS, WRAPPING


def operation(program):
    op = program.operation
    left, right = program.operands
    if op in WRAPPING:
        method = op.removeprefix("wrap_")
        return f"{left}.wrapping_{method}({right})"

    if op in CHECKED_OVERFLOW:
        instruction = op.removeprefix("checked_")
        signed, method = instruction[0] == "s", instruction[1:]
        if signed:
            left, right = f"({left} as i32)", f"{right} as i32"
        error = 1
        guard = ""
    elif op in DIVISION:
        instruction = op.removeprefix("checked_")
        signed, method = instruction[0] == "s", instruction[1:]
        guard = f"if {right} == 0 {{ return 2; }}\n        "
        if signed:
            left, right = f"({left} as i32)", f"{right} as i32"
        error = 1
    elif op in SHIFTS:
        method = "shl" if op == "checked_shl" else "shr"
        left = f"({left} as i32)" if op == "checked_ashr" else left
        guard = ""
        error = 3
    else:
        raise ValueError(f"Unsupported integer operation: {op}")

    return f"{guard}match {left}.checked_{method}({right}) {{ Some(result) => result as u32, None => return {error} }}"


def lower(programs):
    parts = ["#![no_std]\n"]
    for index, program in enumerate(programs):
        result = operation(program)
        parts.append(f"""
// The caller provides a returning callback and an aligned writable output pointer.
#[no_mangle]
pub unsafe extern "C" fn probe_{index}(
    a: u32, b: u32, enabled: u32, emit: extern "C" fn(u32), out: *mut u32,
) -> u32 {{
    emit(a);
    let value = if enabled == 0 {{ b }} else {{
        {result}
    }};
    emit(value);
    unsafe {{ *out = value; }}
    0
}}
""".strip())
    return "\n\n".join(parts) + "\n"
