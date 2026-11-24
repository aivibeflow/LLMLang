"""Lower the admitted Scenario 96A integer fixture to Go."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "PROTOTYPES" / "LLVM-PRESERVATION-01"))
from integer_fixture import CHECKED_OVERFLOW, DIVISION, SHIFTS, WRAPPING


SYMBOLS = {"add": "+", "sub": "-", "mul": "*", "div": "/", "rem": "%"}


def operation(program):
    op = program.operation
    left, right = program.operands
    if op in WRAPPING:
        symbol = SYMBOLS[op.removeprefix("wrap_")]
        return [f"value = {left} {symbol} {right}"]
    if op in CHECKED_OVERFLOW:
        signed, method = op[8] == "s", op[9:]
        symbol = SYMBOLS[method]
        if signed:
            return [f"wide := int64(int32({left})) {symbol} int64(int32({right}))",
                    "if wide < -2147483648 || wide > 2147483647 { return 1 }",
                    "value = uint32(wide)"]
        if method == "sub":
            return [f"if {left} < {right} {{ return 1 }}", f"value = {left} - {right}"]
        return [f"wide := uint64({left}) {symbol} uint64({right})",
                "if wide > 4294967295 { return 1 }", "value = uint32(wide)"]
    if op in DIVISION:
        signed, method = op[8] == "s", op[9:]
        symbol = SYMBOLS[method]
        steps = [f"if {right} == 0 {{ return 2 }}"]
        if signed:
            steps.extend([f"if int32({left}) == -2147483648 && int32({right}) == -1 {{ return 1 }}",
                          f"value = uint32(int32({left}) {symbol} int32({right}))"])
        else:
            steps.append(f"value = {left} {symbol} {right}")
        return steps
    if op in SHIFTS:
        symbol = "<<" if op == "checked_shl" else ">>"
        result = f"{left} {symbol} {right}"
        if op == "checked_ashr":
            result = f"uint32(int32({left}) >> {right})"
        return [f"if {right} >= 32 {{ return 3 }}", f"value = {result}"]
    raise ValueError(f"Unsupported operation {op}")


def lower(programs):
    kernels = ["package main\n"]
    for index, program in enumerate(programs):
        steps = "\n        ".join(operation(program))
        kernels.append(f"""
func kernel{index}(a, b, enabled uint32, emit func(uint32), out *uint32) uint32 {{
    emit(a)
    value := b
    if enabled != 0 {{
        {steps}
    }}
    emit(value)
    *out = value
    return 0
}}
""".strip())
    return "\n\n".join(kernels) + "\n"


def registry(count):
    functions = "\n    ".join(f"kernel{i}," for i in range(count))
    return f"""package main

var kernels = []func(uint32, uint32, uint32, func(uint32), *uint32) uint32{{
    {functions}
}}
"""


def cgo_exports(count):
    wrappers = []
    for i in range(count):
        wrappers.append(f"""
//export probe_{i}
func probe_{i}(a, b, enabled C.uint32_t, emit C.llmlang_emit_t, out *C.uint32_t) C.uint32_t {{
    callback := func(value uint32) {{ C.llmlang_call_emit(emit, C.uint32_t(value)) }}
    slot := (*uint32)(unsafe.Pointer(out))
    return C.uint32_t(kernel{i}(uint32(a), uint32(b), uint32(enabled), callback, slot))
}}
""".strip())
    preamble = """package main

/*
#include <stdint.h>
typedef void (*llmlang_emit_t)(uint32_t);
static inline void llmlang_call_emit(llmlang_emit_t emit, uint32_t value) { emit(value); }
*/
import "C"
import "unsafe"

func main() {}

"""
    return preamble + "\n\n".join(wrappers) + "\n"
