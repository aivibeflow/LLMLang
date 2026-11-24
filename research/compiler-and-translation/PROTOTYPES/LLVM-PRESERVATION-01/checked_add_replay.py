#!/usr/bin/env python3
"""Check exact Scenario 96A LLVM observations across all signed-add inputs."""

import argparse
import ctypes
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from checked_add_formula import Unsupported, conjunction, disagreement, disjunction, form, paths, smt_query
from integer_fixture import SOURCE, compile_source, evaluate
from llvm_integer_probe import CPU, LLVM_VERSION, TRIPLE, _EMIT, _STATUS, _entry, lower


COMPONENTS = ("status", "stores", "effects")
WITNESSES = {
    "drop_overflow": (2147483647, 1, 1),
    "reverse_effects": (2, 3, 0),
    "store_on_error": (2147483647, 1, 1),
}


def run(arguments, stdin=None):
    return subprocess.run(arguments, input=stdin, text=True, check=True, capture_output=True, timeout=60).stdout


def digest(contents):
    return sha256(contents.encode()).hexdigest()


def replace_once(ir, old, new):
    if ir.count(old) != 1:
        raise ValueError(f"Expected exactly one source instruction at {old!r}")
    return ir.replace(old, new)


def variants(ir):
    branch = "  br i1 %overflow, label %overflow_error, label %success\n"
    failed = "overflow_error:\n  ret i32 1\n"
    early = "  call void %emit(i32 %a)\n"
    late = "  call void %emit(i32 %value)\n"
    removed = replace_once(replace_once(ir, branch, "  br label %success\n"), failed, "")
    reordered = replace_once(replace_once(ir, early, ""), late, late + early)
    reordered = replace_once(reordered, failed, "overflow_error:\n" + early + "  ret i32 1\n")
    erroneous_store = replace_once(ir, failed, "overflow_error:\n  store i32 0, ptr %out, align 4\n  ret i32 1\n")
    return {"preserving": ir, "drop_overflow": removed, "reverse_effects": reordered, "store_on_error": erroneous_store}


def native(args, directory, name, level, ir, witness):
    path = directory / name
    source, obj, library = (path.with_suffix(suffix) for suffix in (".ll", ".o", ".so"))
    source.write_text(ir, encoding="utf-8")
    run([args.llc, f"-mtriple={TRIPLE}", f"-mcpu={CPU}", f"-O={level}", "-relocation-model=pic",
         "-filetype=obj", str(source), "-o", str(obj)])
    run([args.cc, "-shared", "-Wl,--no-undefined", "-o", str(library), str(obj)])
    entry = _entry(ctypes.CDLL(str(library)), 0)
    effects = []
    sentinel = 0xabad1234
    output = ctypes.c_uint32(sentinel)
    status = _STATUS[entry(*witness, _EMIT(effects.append), ctypes.byref(output))]
    return {"status": status, "events": effects, "out_slot": output.value}


def solve(args, predicate, expected, witness=None):
    script = smt_query(predicate, witness)
    solvers = {"z3": [args.z3, "-in"], "cvc5": [args.cvc5, "--lang=smt2"]}
    outcomes = {name: run(command, script).strip() for name, command in solvers.items()}
    if any(answer != expected for answer in outcomes.values()):
        raise ValueError(f"Expected {expected}, got {outcomes}\n{script}")
    return {"sha256": digest(script), "outcomes": outcomes}


def check_module(args, directory, name, level, source, source_program):
    ir = run([args.opt, f"-passes=verify,default<O{level}>,verify", "-S", "-o", "-", "-"], source)
    exits = paths(ir)
    guards = [conjunction(*exit.conditions) for exit in exits]
    uncovered = form("not", disjunction(*guards))
    overlaps = (conjunction(left, right) for left, right in combinations(guards, 2))
    all_differ = disagreement(exits, COMPONENTS)
    expected_all = "unsat" if name == "preserving" else "sat"
    expected_without_effects = "unsat" if name in {"preserving", "reverse_effects"} else "sat"
    expected_without_stores = "unsat" if name in {"preserving", "store_on_error"} else "sat"
    record = {
        "ir_sha256": digest(ir),
        "path_count": len(exits),
        "partition": solve(args, disjunction(uncovered, *overlaps), "unsat"),
        "complete_mismatch": solve(args, all_differ, expected_all),
        "status_and_stores_mismatch": solve(args, disagreement(exits, ("status", "stores")),
                                           expected_without_effects),
        "status_and_effects_mismatch": solve(args, disagreement(exits, ("status", "effects")),
                                            expected_without_stores),
    }
    if name == "preserving":
        return record

    witness = WITNESSES[name]
    record["exact_witness_query"] = solve(args, all_differ, "sat", witness)
    a, b, enabled = witness
    reference = evaluate(source_program, a, b, bool(enabled))
    expected = {"status": reference.status, "events": list(reference.events),
                "out_slot": 0xabad1234 if reference.value is None else reference.value}
    observed = native(args, directory, f"{name}-{level}", level, ir, witness)
    expected_changes = {
        "drop_overflow": {"status", "events", "out_slot"},
        "reverse_effects": {"events"},
        "store_on_error": {"out_slot"},
    }
    changed = {field for field in expected if expected[field] != observed[field]}
    if changed != expected_changes[name]:
        raise ValueError(f"Unexpected native observation for {name}: {expected} vs. {observed}")
    return {**record, "witness": witness, "source_observation": expected, "native_observation": observed}


def replay(args):
    versions = {name: run([getattr(args, name), "--version"]).splitlines()[0]
                for name in ("opt", "llc", "cc", "z3", "cvc5")}
    if any(not versions[tool].endswith(f"LLVM version {LLVM_VERSION}") for tool in ("opt", "llc")):
        raise ValueError(f"Expected LLVM {LLVM_VERSION}: {versions}")
    source = SOURCE.replace("operation", "checked_sadd")
    program = compile_source(source)
    ir = lower((program,))
    unknown = replace_once(ir, "entry:\n", "entry:\n  %unmodeled = add nsw i32 %a, %b\n")
    verified = run([args.opt, "-passes=verify,default<O0>,verify", "-S", "-o", "-", "-"], unknown)
    try:
        paths(verified)
    except Unsupported as error:
        if "add nsw" not in str(error):
            raise
    else:
        raise ValueError("An unmodeled arithmetic promise was admitted")
    with TemporaryDirectory(prefix="llmlang-checked-add-") as tmp:
        work = Path(tmp)
        records = {name: {f"O{level}": check_module(args, work, name, level, body, program)
                          for level in (0, 3)} for name, body in variants(ir).items()}
    return {"schema": "llmlang-rt13-checked-add-observations-v1", "tools": versions,
            "source_sha256": digest(source), "unoptimized_ir_sha256": digest(ir), "modules": records,
            "outside_profile": {"ir_sha256": digest(verified), "instruction": "add nsw", "verdict": "unsupported"}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for tool, default in {"opt": "opt-19", "llc": "llc-19", "cc": "cc", "z3": "z3", "cvc5": "cvc5"}.items():
        parser.add_argument(f"--{tool}", default=default)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(replay(args), indent=2) + "\n", encoding="utf-8")
