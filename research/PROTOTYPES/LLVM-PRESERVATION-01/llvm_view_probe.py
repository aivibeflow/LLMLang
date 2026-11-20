"""Compare checked byte-view formation and access with generated LLVM IR."""

import argparse
from collections import Counter
import ctypes
from hashlib import sha256
from itertools import product
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from llvm_integer_probe import LLVM_VERSION, TRIPLE, _build


DATA = bytes((11, 22, 33, 44, 55, 66))
# Two adjacent views, two overlapping views, and an empty view at the end.
VIEWS = ((0, 3), (3, 3), (1, 4), (2, 3), (6, 0))
MIN, MAX = -(2**63), 2**63 - 1
OFFSETS = (MIN, MIN + 1, -7, -1, 0, 1, 2, 3, 4, 5, 6, 7, MAX - 1, MAX)
STATUS = ("ok", "wrong_origin", "overflow", "bounds")


def reference(operation, origin, expected, offset, delta):
    start, length = VIEWS[origin]
    if operation == "read" and origin != expected:
        return "wrong_origin", None
    index = offset + delta
    if index < MIN or index > MAX:
        return "overflow", None
    if operation == "form":
        return ("ok", start + index) if 0 <= index <= length else ("bounds", None)
    if 0 <= index < length:
        return "ok", DATA[start + index]
    return "bounds", None


def lower():
    parts = [
        f'target triple = "{TRIPLE}"',
        "declare { i64, i1 } @llvm.sadd.with.overflow.i64(i64, i64)",
    ]
    for op, comparison in (("form", "ule"), ("read", "ult")):
        origin_guard = (
            "  %same = icmp eq i32 %origin, %expected\n"
            "  br i1 %same, label %add, label %wrong_origin\n"
            "wrong_origin:\n  ret i32 1\n"
            if op == "read" else "  br label %add\n"
        )
        result = (
            "  %byte = load i8, ptr %address, align 1\n"
            "  %value = zext i8 %byte to i64\n"
            if op == "read" else "  %value = ptrtoint ptr %address to i64\n"
        )
        parts.append(f"""
define i32 @{op}_view(ptr %base, i64 %length, i32 %origin, i32 %expected, i64 %offset, i64 %delta, ptr %out) {{
entry:
{origin_guard}add:
  %sum = call {{ i64, i1 }} @llvm.sadd.with.overflow.i64(i64 %offset, i64 %delta)
  %index = extractvalue {{ i64, i1 }} %sum, 0
  %overflowed = extractvalue {{ i64, i1 }} %sum, 1
  br i1 %overflowed, label %overflow, label %bounds_check
overflow:
  ret i32 2
bounds_check:
  %within = icmp {comparison} i64 %index, %length
  br i1 %within, label %valid, label %bounds_error
bounds_error:
  ret i32 3
valid:
  %address = getelementptr inbounds i8, ptr %base, i64 %index
{result}  store i64 %value, ptr %out, align 8
  ret i32 0
}}
""")
    return "\n".join(parts)


def observe(library, slab, operation, origin, expected, offset, delta):
    start, length = VIEWS[origin]
    entry = getattr(library, f"{operation}_view")
    entry.argtypes = [
        ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint32, ctypes.c_uint32,
        ctypes.c_int64, ctypes.c_int64, ctypes.POINTER(ctypes.c_uint64),
    ]
    entry.restype = ctypes.c_uint32
    value = ctypes.c_uint64(2**64 - 1)
    base = ctypes.addressof(slab)
    status = STATUS[entry(base + start, length, origin, expected, offset, delta, ctypes.byref(value))]
    if status != "ok":
        if value.value != 2**64 - 1:
            raise AssertionError("rejected operation changed its output")
        return status, None
    return status, value.value - base if operation == "form" else value.value


def compare(opt, llc, cc):
    for tool in (opt, llc):
        banner = subprocess.check_output([tool, "--version"], text=True, timeout=30).splitlines()[0]
        if not banner.endswith(f"LLVM version {LLVM_VERSION}"):
            raise ValueError(f"expected LLVM {LLVM_VERSION}, got {banner}")
        print(banner)
    slab = (ctypes.c_uint8 * len(DATA)).from_buffer_copy(DATA)
    ir = lower()
    print(f"input LLVM IR sha256 {sha256(ir.encode()).hexdigest()}")
    # Execute each mutant only on its witness. Both mutant loads remain in the
    # initialized physical slab even though they violate the source contract.
    controls = (
        ("one_past_read", ir.replace("icmp ult i64 %index", "icmp ule i64 %index"),
         ("read", 0, 0, 3, 0), ("ok", 44)),
        ("erased_origin", ir.replace("br i1 %same, label %add, label %wrong_origin", "br label %add"),
         ("read", 2, 3, 1, 0), ("ok", 33)),
    )
    with TemporaryDirectory(prefix="llmlang-llvm-views-") as temp:
        for level in (0, 3):
            directory = Path(temp)
            native = _build(ir, opt, llc, cc, level, directory / f"views_O{level}")
            counts = Counter()
            for case in product(("form", "read"), range(len(VIEWS)), range(len(VIEWS)), OFFSETS, OFFSETS):
                wanted = reference(*case)
                actual = observe(native, slab, *case)
                if actual != wanted:
                    raise AssertionError((level, case, wanted, actual))
                counts[actual[0]] += 1
            print(f"O{level} {sum(counts.values())} traces {dict(sorted(counts.items()))}", flush=True)
            # The left one-past address and the right start coincide; their
            # originating views still govern whether a read is permitted.
            seam = (
                observe(native, slab, "form", 0, 0, 3, 0),
                observe(native, slab, "form", 1, 1, 0, 0),
                observe(native, slab, "read", 0, 0, 3, 0),
                observe(native, slab, "read", 1, 1, 0, 0),
            )
            if seam != (("ok", 3), ("ok", 3), ("bounds", None), ("ok", 44)):
                raise AssertionError((level, seam))
            for label, mutant_ir, case, wrong in controls:
                mutant = _build(mutant_ir, opt, llc, cc, level, directory / f"{label}_O{level}")
                observed = observe(mutant, slab, *case)
                wanted = reference(*case)
                if observed != wrong or observed == wanted:
                    raise AssertionError((label, wanted, observed))
                print(f"O{level} {label} {wanted} != {observed}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opt", default="opt-19")
    parser.add_argument("--llc", default="llc-19")
    parser.add_argument("--cc", default="cc")
    args = parser.parse_args()
    compare(args.opt, args.llc, args.cc)
