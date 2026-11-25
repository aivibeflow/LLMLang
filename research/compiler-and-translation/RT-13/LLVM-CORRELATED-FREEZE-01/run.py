"""Check frozen SSA choice correlation against a source contract and LLVM native runs."""

import argparse
import ctypes
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
ROUTES = {
    "single_undef": ("undef", "single"),
    "single_poison": ("poison", "single"),
    "independent_undef": ("undef", "independent"),
    "independent_poison": ("poison", "independent"),
    "inverted_defined": ("poison", "invert"),
    "unsafe_undef": ("undef", "none"),
    "unsafe_poison": ("poison", "none"),
}


def run(args, work):
    return subprocess.run(
        args, cwd=work, env={**os.environ, "LC_ALL": "C", "TZ": "UTC"},
        capture_output=True, check=True, text=True, timeout=30,
    ).stdout.strip()


def digest(data):
    return sha256(data).hexdigest()


def function(name, deferred, selection):
    lines = [
        f"define i32 @{name}(i32 %known, i32 %raw) {{",
        "entry:",
        "  %test = icmp ne i32 %known, 0",
        "  %concrete = trunc i32 %raw to i1",
        f"  %candidate = select i1 %test, i1 %concrete, i1 {deferred}",
    ]
    first = second = "%candidate"
    if selection != "none":
        lines.append("  %choice = freeze i1 %candidate")
        first = second = "%choice"
    if selection == "independent":
        lines.append("  %other = freeze i1 %candidate")
        second = "%other"
    if selection == "invert":
        lines.append("  %other = xor i1 %choice, true")
        second = "%other"
    lines.extend([
        f"  %first = zext i1 {first} to i32",
        f"  %second = zext i1 {second} to i32",
        "  %pair = call i32 @observe_pair(i32 noundef %first, i32 noundef %second)",
        "  ret i32 %pair",
        "}",
    ])
    return "\n".join(lines)


def source_allowed(known, raw):
    return {3 * (raw & 1)} if known else {0, 3}


def abstract_outcomes(known, raw, selection):
    choices = (raw & 1,) if known else (0, 1)
    if selection == "none" and not known:
        return None
    if selection == "independent":
        pairs = product(choices, repeat=2)
    elif selection == "invert":
        pairs = ((value, 1 - value) for value in choices)
    else:
        pairs = ((value, value) for value in choices)
    return {2 * first + second for first, second in pairs}


def abstract_table():
    rows = {}
    for name, (_, selection) in ROUTES.items():
        cases = {}
        for known, raw in product((0, 1), repeat=2):
            values = abstract_outcomes(known, raw, selection)
            key = f"{known}/{raw}"
            cases[key] = None if values is None else sorted(values)
        rows[name] = cases
    assert rows["single_undef"]["0/1"] == rows["single_poison"]["0/1"] == [0, 3]
    assert rows["independent_undef"]["0/1"] == rows["independent_poison"]["0/1"] == [0, 1, 2, 3]
    assert rows["unsafe_undef"]["0/1"] is None and rows["unsafe_poison"]["0/1"] is None
    assert rows["inverted_defined"]["1/0"] == [1] and rows["inverted_defined"]["1/1"] == [2]
    return rows


def execute(path, names, case_data):
    library = ctypes.CDLL(str(path))
    rows = {}
    for name in names:
        selection = ROUTES[name][1] if name in ROUTES else "single"
        native = getattr(library, name)
        native.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        native.restype = ctypes.c_uint32
        seen = {0: set(), 1: set()}
        outside = 0
        withheld = 0
        vector = []
        for known, raw in case_data:
            allowed_by_ir = abstract_outcomes(known, raw, selection)
            if allowed_by_ir is None:
                withheld += 1
                continue
            observed = native(known, raw)
            assert observed in allowed_by_ir, (name, known, raw, observed)
            seen[known].add(observed)
            outside += observed not in source_allowed(known, raw)
            vector.append(observed)
        rows[name] = {
            "executed": len(vector), "withheld": withheld, "outside_source": outside,
            "observed_when_unknown": sorted(seen[0]), "observed_when_known": sorted(seen[1]),
            "native_trace_sha256": digest(bytes(vector)),
        }
    return rows


def collect(args, work):
    source = work / "choice.ll"
    ir = "\n\n".join([
        'target triple = "x86_64-pc-linux-gnu"',
        "declare i32 @observe_pair(i32 noundef, i32 noundef)",
        *(function(name, *settings) for name, settings in ROUTES.items()),
    ]) + "\n"
    source.write_text(ir, encoding="utf-8")
    audit = run([args.lean, HERE / "Choice.lean"], work)
    assert audit.count("does not depend on any axioms") == 5, audit
    vectors = list(product((0, 1), [
        *range(256), 0x7fffffff, 0x80000000, 0xfffffffe, 0xffffffff,
    ]))
    c_library = work / "c-route.so"
    run([args.cc, "-std=c17", "-O2", "-fPIC", "-shared", "-Wl,--no-undefined",
         HERE / "choice.c", "-o", c_library], work)
    portable = execute(c_library, ("portable_choice",), vectors)["portable_choice"]
    assert portable["outside_source"] == portable["withheld"] == 0

    passes = {}
    for pipeline in ("default<O0>", "default<O2>", "default<O3>"):
        optimized = work / "optimized.ll"
        linked = work / f"route-{pipeline[-2]}.so"
        run([args.opt, "-passes=" + pipeline, "-verify-each", "-S", "choice.ll", "-o", optimized], work)
        normalized = optimized.read_text(encoding="utf-8")
        assert normalized.count("define ") == len(ROUTES)
        run([args.clang, "-O0", "-fPIC", "-shared", "-Wl,--no-undefined",
             optimized, HERE / "choice.c", "-o", linked], work)
        rows = execute(linked, ROUTES, vectors)
        for name in ("single_undef", "single_poison"):
            assert rows[name]["outside_source"] == rows[name]["withheld"] == 0
        for name in ("unsafe_undef", "unsafe_poison"):
            assert rows[name]["outside_source"] == 0 and rows[name]["withheld"] == 260
        assert rows["inverted_defined"]["outside_source"] == 520
        passes[pipeline] = {
            "optimized_ir_sha256": digest(optimized.read_bytes()),
            "native_sha256": digest(linked.read_bytes()),
            "remaining_freeze_instructions": normalized.count("freeze i1"),
            "observations": rows,
        }
    return {
        "source_model": "one shared Boolean, explicit fixed value when known",
        "llvm_input_sha256": digest(source.read_bytes()),
        "finite_rule_table": abstract_table(),
        "source_files": {
            name: digest((HERE / name).read_bytes()) for name in ("choice.c", "Choice.lean", "run.py")
        },
        "toolchain": {
            name: run([getattr(args, name), "--version"], work).splitlines()[0]
            for name in ("cc", "clang", "opt", "lean")
        },
        "proof_audit": audit.splitlines(),
        "portable_c": {"native_sha256": digest(c_library.read_bytes()), **portable},
        "inputs_per_native_route": len(vectors),
        "llvm_pipelines": passes,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, default in (("cc", "gcc"), ("clang", "clang"), ("opt", "opt"), ("lean", "lean")):
        parser.add_argument(f"--{name}", default=default)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt13-llvm-freeze-") as temporary:
        evidence = collect(args, Path(temporary))
    args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
