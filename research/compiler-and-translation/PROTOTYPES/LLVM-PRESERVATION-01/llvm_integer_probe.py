"""Compare bounded integer source observations with LLVM 19.1.7 output."""

import argparse
from collections import Counter
import ctypes
from hashlib import sha256
from itertools import product
from pathlib import Path
from random import Random
import subprocess
from tempfile import TemporaryDirectory

from integer_fixture import (
    CHECKED_OVERFLOW, DIVISION, OPERATIONS, SHIFTS, WRAPPING, SOURCE, Observation, Program, compile_source, evaluate,
)


LLVM_VERSION = "19.1.7"
TRIPLE = "x86_64-unknown-linux-gnu"
CPU = "x86-64"
_ERRORS = {"overflow": 1, "zero_divisor": 2, "shift_count": 3}
_STATUS = {0: "ok", **{code: name for name, code in _ERRORS.items()}}
_EMIT = ctypes.CFUNCTYPE(None, ctypes.c_uint32)
_BOUNDARIES = (
    0, 1, 2, 30, 31, 32, 33, 0x3fffffff, 0x40000000, 0x40000001,
    0x7ffffffe, 0x7fffffff, 0x80000000, 0x80000001, 0xffffffdf,
    0xffffffe0, 0xffffffe1, 0xfffffffe, 0xffffffff,
)


def _computation(program: Program) -> tuple[str, str, tuple[str, ...]]:
    """Return the operation blocks, success predecessor and reachable errors."""
    op = program.operation
    x, y = (f"%{name}" for name in program.operands)
    instruction = op.split("_", 1)[1]
    if op in WRAPPING:
        body = f"  %computed = {instruction} i32 {x}, {y}\n  br label %success\n"
        return body, "operation", ()
    if op in CHECKED_OVERFLOW:
        body = f"""\
  %pair = call {{ i32, i1 }} @llvm.{instruction}.with.overflow.i32(i32 {x}, i32 {y})
  %computed = extractvalue {{ i32, i1 }} %pair, 0
  %overflow = extractvalue {{ i32, i1 }} %pair, 1
  br i1 %overflow, label %overflow_error, label %success
"""
        return body, "operation", ("overflow",)
    if op in DIVISION:
        exceptional = "compute"
        errors = ("zero_divisor",)
        signed_guard = ""
        if instruction.startswith("s"):
            exceptional = "check_overflow"
            errors += ("overflow",)
            signed_guard = f"""\
check_overflow:
  %is_min = icmp eq i32 {x}, -2147483648
  %is_neg_one = icmp eq i32 {y}, -1
  %overflow = and i1 %is_min, %is_neg_one
  br i1 %overflow, label %overflow_error, label %compute
"""
        body = f"""\
  %zero = icmp eq i32 {y}, 0
  br i1 %zero, label %zero_divisor_error, label %{exceptional}
{signed_guard}compute:
  %computed = {instruction} i32 {x}, {y}
  br label %success
"""
        return body, "compute", errors
    if op in SHIFTS:
        body = f"""\
  %bounded = icmp ult i32 {y}, 32
  br i1 %bounded, label %compute, label %shift_count_error
compute:
  %computed = {instruction} i32 {x}, {y}
  br label %success
"""
        return body, "compute", ("shift_count",)
    raise ValueError(f"unsupported operation {op}")


def lower(programs: tuple[Program, ...]) -> str:
    intrinsics = sorted({program.operation for program in programs if program.operation in CHECKED_OVERFLOW})
    lines = [f'target triple = "{TRIPLE}"', ""]
    lines.extend(
        f"declare {{ i32, i1 }} @llvm.{op.removeprefix('checked_')}.with.overflow.i32(i32, i32)"
        for op in intrinsics
    )
    for index, program in enumerate(programs):
        body, predecessor, errors = _computation(program)
        exits = "".join(f"{error}_error:\n  ret i32 {_ERRORS[error]}\n" for error in errors)
        lines.append(f"""
define i32 @probe_{index}(i32 %a, i32 %b, i32 %enabled, ptr %emit, ptr %out) {{
entry:
  call void %emit(i32 %a)
  %take_operation = icmp ne i32 %enabled, 0
  br i1 %take_operation, label %operation, label %success
operation:
{body}success:
  %value = phi i32 [ %b, %entry ], [ %computed, %{predecessor} ]
  call void %emit(i32 %value)
  store i32 %value, ptr %out, align 4
  ret i32 0
{exits}}}
""")
    return "\n".join(lines)


def _build(ir: str, opt: str, llc: str, cc: str, level: int, path: Path) -> ctypes.CDLL:
    optimized = path.with_suffix(".ll")
    obj = path.with_suffix(".o")
    library = path.with_suffix(".so")
    subprocess.run([opt, f"-passes=verify,default<O{level}>,verify", "-S", "-o", str(optimized), "-"],
                   input=ir, text=True, check=True, timeout=60)
    subprocess.run([llc, f"-mtriple={TRIPLE}", f"-mcpu={CPU}", f"-O={level}", "-relocation-model=pic",
                    "-filetype=obj", str(optimized), "-o", str(obj)], check=True, timeout=60)
    subprocess.run([cc, "-shared", "-Wl,--no-undefined", "-o", str(library), str(obj)], check=True, timeout=60)
    return ctypes.CDLL(str(library))


def _entry(library: ctypes.CDLL, index: int):
    entry = getattr(library, f"probe_{index}")
    entry.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, _EMIT, ctypes.POINTER(ctypes.c_uint32)]
    entry.restype = ctypes.c_uint32
    return entry


def _observe(entry, a: int, b: int, enabled: bool) -> Observation:
    events = []
    sentinel = 0xabad1234
    value = ctypes.c_uint32(sentinel)
    status = _STATUS[entry(a, b, enabled, _EMIT(events.append), ctypes.byref(value))]
    if status != "ok" and value.value != sentinel:
        raise AssertionError(f"unexpected result store on {status}")
    return Observation(status, value.value if status == "ok" else None, tuple(events))


def _check_rejections(opt: str, lower_checked: str) -> None:
    non_dominating = lower_checked.replace("ret i32 1", "ret i32 %value", 1)
    rejected = subprocess.run([opt, "-passes=verify", "-disable-output", "-"],
                              input=non_dominating, capture_output=True, text=True, timeout=60)
    if rejected.returncode == 0 or "does not dominate" not in rejected.stderr:
        raise AssertionError(f"verifier did not diagnose the non-dominating value\n{rejected.stderr}")
    sources = (
        SOURCE.replace("operation(a, b)", "unchecked_sdiv(a, b)"),
        SOURCE.replace("operation(a, b)", "wrap_add(a, 1)"),
        SOURCE.replace("operation", "wrap_add").replace("emit(value)", "emit(value + 1)"),
    )
    for source in sources:
        try:
            compile_source(source)
        except ValueError:
            continue
        raise AssertionError(f"unsupported source accepted\n{source}")
    print(f"{len(sources)} unsupported sources and one invalid dominance relation rejected", flush=True)


def compare(opt: str, llc: str, cc: str) -> None:
    for tool in (opt, llc):
        version = subprocess.check_output([tool, "--version"], text=True, timeout=30).splitlines()[0]
        if not version.endswith(f"LLVM version {LLVM_VERSION}"):
            raise ValueError(f"expected LLVM {LLVM_VERSION}, got {version}")
        print(f"{Path(tool).name} {version}", flush=True)
    print(subprocess.check_output([cc, "--version"], text=True, timeout=30).splitlines()[0], flush=True)

    sources = tuple(SOURCE.replace("operation", operation) for operation in OPERATIONS)
    sources += (SOURCE.replace("operation(a, b)", "checked_sdiv(b, a)"),)
    programs = tuple(map(compile_source, sources))
    ir = lower(programs)
    print(f"input LLVM IR sha256 {sha256(ir.encode()).hexdigest()}", flush=True)

    random = Random(134)
    sampled = tuple((random.getrandbits(32), random.getrandbits(32)) for _ in range(256))
    pairs = (*product(_BOUNDARIES, repeat=2), *sampled)
    inputs = tuple((a, b, enabled) for (a, b), enabled in product(pairs, (False, True)))
    checked = compile_source(SOURCE.replace("operation", "checked_sadd"))
    lower_checked = lower((checked,))
    _check_rejections(opt, lower_checked)
    bad_lowering = lower_checked.replace("br i1 %overflow, label %overflow_error, label %success", "br label %success")
    witness = (0x7fffffff, 1, True)
    reference = evaluate(checked, *witness)

    with TemporaryDirectory(prefix="llmlang-llvm-integers-") as directory:
        for level in (0, 3):
            native = _build(ir, opt, llc, cc, level, Path(directory) / f"probe_O{level}")
            counts = Counter()
            for index, program in enumerate(programs):
                entry = _entry(native, index)
                for case in inputs:
                    expected = evaluate(program, *case)
                    observed = _observe(entry, *case)
                    if expected != observed:
                        raise AssertionError(f"O{level} {program} {case}\nreference {expected}\nnative {observed}")
                    counts[observed.status] += 1
            print(f"O{level} {len(programs)} programs  {sum(counts.values())} traces  {dict(sorted(counts.items()))}", flush=True)
            mutant = _build(bad_lowering, opt, llc, cc, level, Path(directory) / f"negative_O{level}")
            observed = _observe(_entry(mutant, 0), *witness)
            if observed == reference:
                raise AssertionError("checked-overflow negative control escaped differential comparison")
            print(f"O{level} valid IR with missing overflow branch disagrees  {reference} != {observed}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opt", default="opt-19")
    parser.add_argument("--llc", default="llc-19")
    parser.add_argument("--cc", default="cc")
    args = parser.parse_args()
    compare(args.opt, args.llc, args.cc)
