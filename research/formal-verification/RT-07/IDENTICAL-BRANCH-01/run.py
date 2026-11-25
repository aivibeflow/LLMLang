#!/usr/bin/env python3
"""Check common-branch elimination with scoped complete observations."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
FALSE, TRUE, ERROR, DIVERGE, CANCEL, RETURN = range(6)
GUARDS = tuple(product(range(3), range(5), range(2), range(5)))
BODIES = range(6)
VARIANTS = ("original", "sequence", "erase", "duplicate")


def guard(cell, update, visible):
    new = (cell, 0, 1, 2, (cell + 1) % 3)[update]
    return new, (new,) if visible else ()


def evaluate(case, body, variant):
    initial, update, visible, status = case
    state, history = initial, ()
    if variant != "erase":
        state, history = guard(initial, update, visible)
        if status in (ERROR, DIVERGE, CANCEL):
            return status, 0, state, *history
    if variant == "duplicate":
        state, second = guard(state, update, visible)
        history += second
    observations = (
        (RETURN, state, state, *history),
        (RETURN, 0, state, *history),
        (RETURN, 0, 0, *history, 3),
        (ERROR, 0, state, *history),
        (DIVERGE, 0, state, *history),
        (CANCEL, 0, state, *history),
    )
    return observations[body]


def text_row(row):
    return " ".join(map(str, row))


def check_native(inputs, outputs):
    clang = os.environ.get("CLANG", "clang")
    build = {}
    data = "\n".join(map(text_row, inputs)) + "\n"
    expected = "\n".join(map(text_row, outputs)) + "\n"
    native_version = subprocess.check_output([clang, "--version"], text=True).splitlines()[0]
    with tempfile.TemporaryDirectory() as directory:
        for level in ("O0", "O3"):
            flags = [f"-{level}", "-std=c11", "-Wall", "-Wextra", "-Werror"]
            ir = Path(directory) / f"{level}.ll"
            executable = Path(directory) / f"{level}.out"
            subprocess.run([clang, *flags, "-S", "-emit-llvm", "fixture.c", "-o", str(ir)],
                           cwd=HERE, check=True)
            subprocess.run([clang, str(ir), "-o", str(executable)], check=True)
            proc = subprocess.run([str(executable)], input=data, text=True,
                                  capture_output=True, check=True)
            if proc.stdout != expected or proc.stderr:
                raise AssertionError(f"Unexpected native observations under {level}")
            build[level] = {"rows": len(outputs), "ir_sha256": sha256(ir.read_bytes()).hexdigest(),
                            "stdout_sha256": sha256(proc.stdout.encode()).hexdigest()}
    return {"compiler": native_version, "builds": build}


def compare():
    counts, witnesses = Counter(), {}
    inputs, outputs = [], []
    for case in GUARDS:
        initial, update, visible, status = case
        state, history = guard(initial, update, visible)
        can_erase = status in (FALSE, TRUE) and state == initial and not history
        universal = True
        for body in BODIES:
            original, seq, erased, duplicate = rows = tuple(
                evaluate(case, body, variant) for variant in VARIANTS)
            if original != seq:
                raise AssertionError((case, body, rows))
            universal &= original == erased
            counts["body_comparisons"] += 1
            counts["erase_changes_observation"] += original != erased
            counts["erase_only_changes_trace"] += original[:3] == erased[:3] and original != erased
            counts["duplicate_changes_observation"] += original != duplicate
            if original[:3] == erased[:3] and original != erased:
                witnesses.setdefault("trace_only_erasure", [case, body, original, erased])
            if original[0] == DIVERGE and erased[0] == RETURN:
                witnesses.setdefault("removed_divergence", [case, body, original, erased])
            inputs.append((*case, body))
            outputs.extend(rows)
        if universal != can_erase:
            raise AssertionError(f"Guard erasure precondition failed for {case}")
        counts["guards"] += 1
        counts["universally_erasable_guards"] += universal
    return counts, witnesses, inputs, outputs


if __name__ == "__main__":
    counts, witnesses, inputs, outputs = compare()
    print(json.dumps({
        "schema": "llmlang-identical-branch/1", "python": platform.python_version(),
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("Rewrite.lean", "axioms.txt", "fixture.c", "run.py")},
        "counts": counts, "witnesses": witnesses, "native": check_native(inputs, outputs),
    }, indent=2))
