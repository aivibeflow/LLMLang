"""Compare transactional byte-view access and aliasing across LLVM and C++."""

import argparse
from collections import Counter
import ctypes
from hashlib import sha256
from itertools import product
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from llvm_integer_probe import LLVM_VERSION, TRIPLE, _build
from llvm_view_probe import DATA, MAX, MIN, OFFSETS, STATUS, VIEWS


SENTINEL = 0xFFFF
WRITE_VALUE = 201
BYTE_PTR = ctypes.POINTER(ctypes.c_uint8)


def reference(write_view, read_view, write_expected, read_expected, offset, delta, probe_index):
    slab = bytearray(DATA)
    locations = []
    for view, expected, index in (
        (write_view, write_expected, offset + delta), (read_view, read_expected, probe_index),
    ):
        if view != expected:
            return "wrong_origin", SENTINEL, bytes(slab)
        if not MIN <= index <= MAX:
            return "overflow", SENTINEL, bytes(slab)
        start, length = VIEWS[view]
        if not 0 <= index < length:
            return "bounds", SENTINEL, bytes(slab)
        locations.append(start + index)
    write_at, read_at = locations
    before = slab[read_at]
    slab[write_at] = WRITE_VALUE
    return "ok", (before << 8) | slab[read_at], bytes(slab)


def lower_llvm():
    return f"""target triple = "{TRIPLE}"
declare {{ i64, i1 }} @llvm.sadd.with.overflow.i64(i64, i64)

define i32 @mutate_view(ptr %write_base, ptr %read_base, i64 %write_len, i64 %read_len,
                       i32 %write_origin, i32 %read_origin, i32 %write_expected,
                       i32 %read_expected, i64 %offset, i64 %delta, i64 %probe,
                       i8 %byte, ptr %out) {{
entry:
  %write_identity = icmp eq i32 %write_origin, %write_expected
  br i1 %write_identity, label %checked_add, label %wrong_origin
checked_add:
  %sum = call {{ i64, i1 }} @llvm.sadd.with.overflow.i64(i64 %offset, i64 %delta)
  %write_index = extractvalue {{ i64, i1 }} %sum, 0
  %overflow = extractvalue {{ i64, i1 }} %sum, 1
  br i1 %overflow, label %overflow_error, label %write_bounds
write_bounds:
  %write_valid = icmp ult i64 %write_index, %write_len
  br i1 %write_valid, label %read_identity_check, label %bounds_error
read_identity_check:
  %read_identity = icmp eq i32 %read_origin, %read_expected
  br i1 %read_identity, label %read_bounds, label %wrong_origin
read_bounds:
  %read_valid = icmp ult i64 %probe, %read_len
  br i1 %read_valid, label %perform, label %bounds_error
perform:
  %src = getelementptr inbounds i8, ptr %read_base, i64 %probe
  %dest = getelementptr inbounds i8, ptr %write_base, i64 %write_index
  %before = load i8, ptr %src, align 1
  store i8 %byte, ptr %dest, align 1
  %after = load i8, ptr %src, align 1
  %before_wide = zext i8 %before to i16
  %after_wide = zext i8 %after to i16
  %high = shl i16 %before_wide, 8
  %result = or i16 %high, %after_wide
  store i16 %result, ptr %out, align 2
  ret i32 0
wrong_origin:
  ret i32 1
overflow_error:
  ret i32 2
bounds_error:
  ret i32 3
}}
"""


CPP = """#include <cstdint>

extern "C" std::uint32_t mutate_view(
    std::uint8_t* write_base, const std::uint8_t* read_base,
    std::uint64_t write_len, std::uint64_t read_len,
    std::uint32_t write_origin, std::uint32_t read_origin,
    std::uint32_t write_expected, std::uint32_t read_expected,
    std::int64_t offset, std::int64_t delta, std::int64_t probe,
    std::uint8_t byte, std::uint16_t* out) {
    if (write_origin != write_expected) return 1;
    std::int64_t index;
    if (__builtin_add_overflow(offset, delta, &index)) return 2;
    if (index < 0 || static_cast<std::uint64_t>(index) >= write_len) return 3;
    if (read_origin != read_expected) return 1;
    if (probe < 0 || static_cast<std::uint64_t>(probe) >= read_len) return 3;

    const auto before = read_base[probe];
    write_base[index] = byte;
    const auto after = read_base[probe];
    *out = (static_cast<std::uint16_t>(before) << 8) | after;
    return 0;
}
"""


def observe(entry, write_view, read_view, write_expected, read_expected, offset, delta, probe):
    slab = (ctypes.c_uint8 * len(DATA)).from_buffer_copy(DATA)
    write_start, write_len = VIEWS[write_view]
    read_start, read_len = VIEWS[read_view]
    base = ctypes.addressof(slab)
    output = ctypes.c_uint16(SENTINEL)
    status = entry(
        ctypes.cast(base + write_start, BYTE_PTR), ctypes.cast(base + read_start, BYTE_PTR),
        write_len, read_len, write_view, read_view, write_expected, read_expected,
        offset, delta, probe, WRITE_VALUE, ctypes.byref(output),
    )
    return STATUS[status], output.value, bytes(slab)


def entry(library):
    access = library.mutate_view
    access.argtypes = [BYTE_PTR, BYTE_PTR, ctypes.c_uint64, ctypes.c_uint64,
                       *([ctypes.c_uint32] * 4), *([ctypes.c_int64] * 3),
                       ctypes.c_uint8, ctypes.POINTER(ctypes.c_uint16)]
    access.restype = ctypes.c_uint32
    return access


def corpus():
    for write, read, wrong_write, wrong_read, offset, delta, probe in product(
        range(len(VIEWS)), range(len(VIEWS)), (False, True), (False, True),
        OFFSETS, OFFSETS, (-1, 0, 1, 2, 3, 4),
    ):
        yield (write, read, (write + wrong_write) % len(VIEWS),
               (read + wrong_read) % len(VIEWS), offset, delta, probe)


def run(opt, llc, cc, cxx):
    for tool in (opt, llc):
        banner = subprocess.check_output([tool, "--version"], text=True, timeout=30).splitlines()[0]
        if not banner.endswith(f"LLVM version {LLVM_VERSION}"):
            raise ValueError(f"expected LLVM {LLVM_VERSION}, got {banner}")
        print(banner)
    print(subprocess.check_output([cxx, "--version"], text=True, timeout=30).splitlines()[0])
    ir = lower_llvm()
    print(f"LLVM IR SHA-256 {sha256(ir.encode()).hexdigest()}")
    print(f"C++ source SHA-256 {sha256(CPP.encode()).hexdigest()}")
    cases = [(case, reference(*case)) for case in corpus()]
    counts = Counter(expected[0] for _, expected in cases)
    print(f"{len(cases)} cases per build, status counts {dict(sorted(counts.items()))}")

    with TemporaryDirectory(prefix="llmlang-llvm-mutable-views-") as temp:
        directory = Path(temp)
        cpp = directory / "views.cpp"
        cpp.write_text(CPP, encoding="utf-8")
        for level in (0, 3):
            llvm = _build(ir, opt, llc, cc, level, directory / f"llvm{level}")
            cxx_library = directory / f"cpp{level}.so"
            subprocess.run([cxx, "-std=c++20", f"-O{level}", "-shared", "-fPIC",
                            "-o", str(cxx_library), str(cpp)], check=True, timeout=60)
            for name, library in (("LLVM", llvm), ("C++", ctypes.CDLL(str(cxx_library)))):
                access = entry(library)
                for case, expected in cases:
                    actual = observe(access, *case)
                    if actual != expected:
                        raise AssertionError((name, level, case, expected, actual))
                print(f"{name} O{level}: {len(cases)} match")

        witness = (2, 3, 2, 3, 1, 0, 0)
        expected = reference(*witness)
        noalias = ir.replace("ptr %write_base, ptr %read_base", "ptr noalias %write_base, ptr %read_base")
        for level in (0, 3):
            mutant = _build(noalias, opt, llc, cc, level, directory / f"noalias{level}")
            actual = observe(entry(mutant), *witness)
            print(f"noalias O{level}: expected {expected}, got {actual}")
            if level == 3 and (actual[0], actual[2]) != (expected[0], expected[2]):
                raise AssertionError("noalias control did not preserve status and final memory")
            if level == 3 and actual[1] != (DATA[2] << 8) | DATA[2]:
                raise AssertionError("noalias control did not reuse the stale before-byte")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opt", required=True)
    parser.add_argument("--llc", required=True)
    parser.add_argument("--cc", default="cc")
    parser.add_argument("--cxx", default="c++")
    args = parser.parse_args()
    run(args.opt, args.llc, args.cc, args.cxx)
