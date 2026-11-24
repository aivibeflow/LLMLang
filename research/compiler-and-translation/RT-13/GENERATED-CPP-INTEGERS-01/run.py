"""Replay checked integer outputs through GCC and Clang C++ objects."""

import argparse
import ctypes
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from lower_cpp import lower


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "GENERATED-RUST-INTEGERS-01"))
from run import (FIXTURE, change, check_profile, execute, link, observe, program_source, reference, vectors)
from integer_fixture import OPERATIONS, compile_source
from llvm_integer_probe import _entry


def object_file(compiler, level, directory, name, source):
    path = directory / f"{name}.cc"
    obj = path.with_suffix(".o")
    path.write_text(source, encoding="utf-8")
    execute(compiler, "-std=c++20", "-m64", "-march=x86-64", "-fPIC", "-fno-exceptions", "-fno-rtti",
            "-Wall", "-Wextra", "-Werror", f"-O{level}", "-c", path, "-o", obj)
    return obj


def controls(args, directory):
    cases = (
        ("wrapped_overflow", "checked_sadd", (0x7fffffff, 1, 1),
         "        if (wide < -2147483648LL || wide > 2147483647LL) return 1;\n", "", {"status", "slot", "events"}),
        ("masked_shift", "checked_shl", (7, 32, 1),
         "        if (b >= 32u) return 3;\n        value = a << b;",
         "        value = a << (b & 31u);", {"status", "slot", "events"}),
        ("reverse_callbacks", "checked_sadd", (7, 2, 1), "    emit(a);\n", "", {"events"}),
        ("writes_on_error", "checked_sadd", (0x7fffffff, 1, 1),
         "        if (wide < -2147483648LL || wide > 2147483647LL) return 1;",
         "        if (wide < -2147483648LL || wide > 2147483647LL) { *out = 0; return 1; }", {"slot"}),
    )
    output = {}
    for name, operation, inputs, anchor, replacement, wanted in cases:
        program = compile_source(program_source(operation))
        code = change(lower((program,)), anchor, replacement)
        if name == "reverse_callbacks":
            code = change(code, "    emit(value);", "    emit(value);\n    emit(a);")
        obj = object_file(args.gxx, 3, directory, name, code)
        target = ctypes.CDLL(str(link(args, obj)))
        expected = reference(program, inputs)
        observed = observe(_entry(target, 0), inputs)
        seen = {key for key, a, b in zip(("status", "slot", "events"), expected, observed, strict=True) if a != b}
        if seen != wanted:
            raise AssertionError((name, wanted, seen, expected, observed))
        output[name] = {"input": inputs, "expected": expected, "actual": observed, "changed": sorted(seen)}
    return output


def verify(options):
    tools = {name: execute(getattr(options, name), "--version").splitlines()[0]
             for name in ("gxx", "clangxx", "cc", "nm")}
    if "14.2.0" not in tools["gxx"] or "clang version 19.1.7" not in tools["clangxx"]:
        raise ValueError(f"Unexpected toolchains: {tools}")
    programs = tuple(compile_source(program_source(op, left, right))
                     for op, (left, right) in product(OPERATIONS, product("ab", repeat=2)))
    cases = vectors()
    expected = tuple(tuple(reference(program, case) for case in cases) for program in programs)
    code = lower(programs)
    profiles = {}
    with TemporaryDirectory(prefix="llmlang-cpp-integers-") as temporary:
        root = Path(temporary)
        for compiler, level in product(("gxx", "clangxx"), (0, 3)):
            name = f"{compiler}_O{level}"
            obj = object_file(getattr(options, compiler), level, root, name, code)
            profiles[name] = check_profile(options, obj, programs, cases, expected)
        mutants = controls(options, root)
    sources = {p.name: sha256(p.read_bytes()).hexdigest() for p in (
        FIXTURE / "integer_fixture.py", FIXTURE / "llvm_integer_probe.py", HERE / "lower_cpp.py", Path(__file__),
    )}
    return {"format": "rt13-cpp-checked-integers/1", "python": sys.version.split()[0], "tools": tools,
            "programs": len(programs), "vectors": len(cases), "input_sha256": sources,
            "generated_cpp_sha256": sha256(code.encode()).hexdigest(), "profiles": profiles, "controls": mutants}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gxx", default="g++")
    parser.add_argument("--clangxx", default="clang++-19")
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--nm", default="llvm-nm-19")
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    options.output.write_text(json.dumps(verify(options), indent=2, sort_keys=True) + "\n", encoding="utf-8")
