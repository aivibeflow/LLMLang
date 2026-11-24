"""Cross-check the same bounded source programs through direct LLVM and Rust."""

import argparse
from collections import Counter
import ctypes
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
from random import Random
import re
import subprocess
from tempfile import TemporaryDirectory

from lower_rust import lower
from integer_fixture import OPERATIONS, SOURCE, compile_source, evaluate
from llvm_integer_probe import (
    CPU, TRIPLE, _BOUNDARIES, _EMIT, _entry, _STATUS, lower as lower_llvm,
)


HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parents[1] / "PROTOTYPES" / "LLVM-PRESERVATION-01"
SENTINEL = 0xabad1234


def execute(*arguments, stdin=None):
    run = subprocess.run(list(map(str, arguments)), input=stdin, text=True, capture_output=True, timeout=120)
    if run.returncode or run.stderr:
        raise ValueError(f"Tool failed: {arguments!r}\n{run.stdout}\n{run.stderr}")
    return run.stdout


def program_source(operation, left="a", right="b"):
    return SOURCE.replace("operation(a, b)", f"{operation}({left}, {right})")


def vectors():
    rng = Random(134)
    pairs = [*product(_BOUNDARIES, repeat=2),
             *((rng.getrandbits(32), rng.getrandbits(32)) for _ in range(256))]
    return tuple((a, b, enabled) for (a, b), enabled in product(pairs, (0, 1, 2, 0x80000000, 0xffffffff)))


def reference(program, case):
    a, b, enabled = case
    seen = evaluate(program, a, b, bool(enabled))
    return seen.status, SENTINEL if seen.value is None else seen.value, seen.events


def observe(entry, case):
    out = ctypes.c_uint32(SENTINEL)
    events = []
    status = entry(*case, _EMIT(events.append), ctypes.byref(out))
    return _STATUS[status], out.value, tuple(events)


def rust_object(args, work, source, level, label, debug=False):
    path = work / f"{label}.rs"
    obj = path.with_suffix(".o")
    path.write_text(source, encoding="utf-8")
    execute(args.rustc, "--target", TRIPLE, "--edition", "2021", "--crate-type", "lib",
            "--crate-name", "llmlang_probe", "--emit", "obj", "-D", "warnings",
            "-C", "panic=abort", "-C", f"debug-assertions={'yes' if debug else 'no'}",
            "-C", f"opt-level={level}", "-C", f"target-cpu={CPU}", "-C", "relocation-model=pic",
            "--remap-path-prefix", f"{work}=/fixture", path, "-o", obj)
    return obj


def llvm_object(args, work, source, level):
    optimized = work / f"llvm-O{level}.ll"
    obj = optimized.with_suffix(".o")
    execute(args.opt, f"-passes=verify,default<O{level}>,verify", "-S", "-o", optimized, "-", stdin=source)
    execute(args.llc, f"-mtriple={TRIPLE}", f"-mcpu={CPU}", f"-O={level}", "-relocation-model=pic",
            "-filetype=obj", optimized, "-o", obj)
    return obj


def imports(args, obj):
    return execute(args.nm, "--demangle", "--undefined-only", obj).splitlines()


def link(args, obj):
    library = obj.with_suffix(".so")
    undefined = imports(args, obj)
    if undefined:
        raise ValueError(f"Unexpected undefined object symbols: {undefined}")
    execute(args.cc, "-shared", "-Wl,--no-undefined", "-o", library, obj)
    return library


def artifact_facts(args, obj, library, count):
    facts = {}
    for line in execute(args.nm, "--print-size", "--defined-only", library).splitlines():
        match = re.fullmatch(r"([0-9a-f]+) ([0-9a-f]+) T probe_(\d+)", line)
        if match:
            facts[int(match[3])] = (int(match[1], 16), int(match[2], 16))
    if set(facts) != set(range(count)):
        raise ValueError(f"Missing exports: {facts}")
    machine = set(facts.values())
    return {
        "exports": len(facts), "distinct_exported_extents": len(machine),
        "exported_extent_sum_bytes": sum(size for _, size in machine),
        "object_bytes": obj.stat().st_size, "object_sha256": sha256(obj.read_bytes()).hexdigest(),
        "undefined_obj_symbols": [],
    }


def check_profile(args, obj, programs, cases, expected):
    library = link(args, obj)
    binary = ctypes.CDLL(str(library))
    counts = Counter()
    for i, program in enumerate(programs):
        entry = _entry(binary, i)
        for case, wanted in zip(cases, expected[i], strict=True):
            returned = observe(entry, case)
            if returned != wanted:
                raise AssertionError(f"{program}, {case}: got {returned}, expected {wanted}")
            counts[returned[0]] += 1
    return {**artifact_facts(args, obj, library, len(programs)), "observations": sum(counts.values()),
            "statuses": dict(sorted(counts.items()))}


def change(source, anchor, replacement):
    if source.count(anchor) != 1:
        raise ValueError(f"Expected one negative-control anchor: {anchor!r}")
    return source.replace(anchor, replacement)


def negative(args, work):
    overflowing = (0x7fffffff, 1, 1)
    cases = (
        ("wrapped_signed_overflow", "checked_sadd", overflowing,
         (("match (a as i32).checked_add(b as i32) { Some(result) => result as u32, None => return 1 }",
           "(a as i32).wrapping_add(b as i32) as u32"),), {"status", "slot", "events"}),
        ("masked_shift_count", "checked_shl", (7, 32, 1),
         (("match a.checked_shl(b) { Some(result) => result as u32, None => return 3 }",
           "a.wrapping_shl(b)"),), {"status", "slot", "events"}),
        ("wrong_zero_divisor_status", "checked_sdiv", (7, 0, 1),
         (("if b == 0 { return 2; }", "if b == 0 { return 1; }"),), {"status"}),
        ("write_after_overflow", "checked_sadd", overflowing,
         (("None => return 1", "None => { unsafe { *out = 0; } return 1; }"),), {"slot"}),
        ("reverse_effects", "checked_sadd", (7, 2, 1),
         (("    emit(a);\n", ""), ("    emit(value);", "    emit(value);\n    emit(a);")), {"events"}),
    )
    result = {}
    for label, operation, witness, replacements, fields in cases:
        program = compile_source(program_source(operation))
        mutant = lower((program,))
        for anchor, replacement in replacements:
            mutant = change(mutant, anchor, replacement)
        obj = rust_object(args, work, mutant, 3, label)
        library = ctypes.CDLL(str(link(args, obj)))
        expected = reference(program, witness)
        actual = observe(_entry(library, 0), witness)
        changed = {key for key, old, new in zip(("status", "slot", "events"), expected, actual, strict=True)
                   if old != new}
        if changed != fields:
            raise AssertionError(f"Negative control {label} changed {changed}")
        result[label] = {"input": witness, "expected": expected, "actual": actual,
                         "changed": sorted(changed)}
    return result


def main(args):
    tools = {name: execute(getattr(args, name), "--version").splitlines()[0]
             for name in ("opt", "llc", "cc", "rustc", "nm")}
    rust_version = execute(args.rustc, "-vV")
    if ("release: 1.85.1" not in rust_version or "LLVM version: 19.1.7" not in rust_version
        or any(not tools[name].endswith("LLVM version 19.1.7") for name in ("opt", "llc"))):
        raise ValueError(f"Unexpected toolchain {tools}\n{rust_version}")

    programs = tuple(compile_source(program_source(op, left, right))
                     for op, (left, right) in product(OPERATIONS, product("ab", repeat=2)))
    cases = vectors()
    expected = tuple(tuple(reference(program, case) for case in cases) for program in programs)
    rust, llvm = lower(programs), lower_llvm(programs)
    with TemporaryDirectory(prefix="llmlang-rust-integers-") as directory:
        work = Path(directory)
        results = {}
        for level in (0, 3):
            objects = {"llvm": llvm_object(args, work, llvm, level),
                       "rust": rust_object(args, work, rust, level, f"rust-O{level}")}
            for name, obj in objects.items():
                results[f"{name}_O{level}"] = check_profile(args, obj, programs, cases, expected)
        debug = rust_object(args, work, rust, 0, "rust-debug-checks", debug=True)
        controls = negative(args, work)
        debug_imports = [row.strip().removeprefix("U ") for row in imports(args, debug)]
        debug_link = subprocess.run(
            [args.cc, "-shared", "-Wl,--no-undefined", "-o", str(debug.with_suffix(".so")), str(debug)],
            text=True, capture_output=True, timeout=60,
        )
        if (len(debug_imports) != 1 or "core::panicking::panic_nounwind" not in debug_imports[0]
                or debug_link.returncode == 0 or "panic_nounwind" not in debug_link.stderr):
            raise ValueError(f"Debug object did not establish the expected runtime dependency: {debug_imports!r}")
    return {
        "tools": tools, "rust_build": rust_version.splitlines(), "target": TRIPLE, "cpu": CPU,
        "programs": len(programs), "vectors": len(cases),
        "lowered_sha256": {"llvm": sha256(llvm.encode()).hexdigest(), "rust": sha256(rust.encode()).hexdigest()},
        "input_sources_sha256": {
            path.name: sha256(path.read_bytes()).hexdigest()
            for path in (HERE / "run.py", HERE / "lower_rust.py", FIXTURE / "integer_fixture.py",
                         FIXTURE / "llvm_integer_probe.py")},
        "profiles": results, "controls": controls, "rust_O0_debug_assertions_imports": debug_imports,
        "rust_O0_debug_link_without_runtime_rejected": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option, default in (("rustc", "rustc"), ("opt", "opt-19"), ("llc", "llc-19"),
                            ("cc", "gcc"), ("nm", "llvm-nm-19")):
        parser.add_argument(f"--{option}", default=default)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(main(args), sort_keys=True, indent=2) + "\n", encoding="utf-8")
