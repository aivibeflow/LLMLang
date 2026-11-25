#!/usr/bin/env python3
"""Compare native call traces against declarative operand schedules."""

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
CASES = tuple(product(range(2), range(4), range(4), range(4)))
LEFT_FIRST = (0, 1, 2)
RIGHT_FIRST = (0, 2, 1)


def evaluate(case, order):
    cell, *behaviors = case
    trace = []
    values = [None] * 3
    for stage in order:
        behavior = behaviors[stage]
        before = cell
        if behavior in (1, 2):
            cell ^= 1
        trace.append(4 * stage + 2 * before + cell)
        if behavior >= 2:
            return ("error", stage, cell, *trace)
        values[stage] = cell
    trace.append(12 + 3 * cell)
    return ("return", 2 * values[1] + values[2], cell, *trace)


def text_row(row):
    return " ".join(map(str, row))


def native(oracles):
    rust = os.environ.get("RUSTC", "rustc")
    gcc = os.environ.get("GXX", "g++")
    clang = os.environ.get("CLANGXX", "clang++")
    compilers = {
        "rust": (rust, "--edition=2021", "-Copt-level="),
        "gcc": (gcc, "-std=c++20", "-O"),
        "clang": (clang, "-std=c++20", "-O"),
    }
    records = {}
    data = "\n".join(map(text_row, CASES)) + "\n"
    with tempfile.TemporaryDirectory() as build:
        for lang, (compiler, mode, opt) in compilers.items():
            version = subprocess.check_output([compiler, "--version"], text=True).splitlines()[0]
            fixture = "call.rs" if lang == "rust" else "call.cc"
            for level in ("0", "2"):
                target = Path(build) / f"{lang}-{level}"
                subprocess.run([compiler, mode, f"{opt}{level}", str(HERE / fixture),
                                "-o", str(target)], check=True)
                proc = subprocess.run([str(target)], input=data, capture_output=True,
                                      text=True, check=True)
                rows = proc.stdout.splitlines()
                if proc.stderr or len(rows) != len(CASES):
                    raise AssertionError(f"{lang}-{level} failed to return the expected row count")
                count = Counter()
                for case, observed, (left, right) in zip(CASES, rows, oracles, strict=True):
                    allowed = {text_row(left)} if lang == "rust" else {text_row(left), text_row(right)}
                    if observed not in allowed:
                        raise AssertionError((lang, level, case, observed, allowed))
                    left_seen = observed == text_row(left)
                    right_seen = observed == text_row(right)
                    count["matches_both"] += left_seen and right_seen
                    count["left_only"] += left_seen and not right_seen
                    count["right_only"] += right_seen and not left_seen
                records[f"{lang}-O{level}"] = {
                    "version": version, "rows": len(rows), "matches": count,
                    "stdout_sha256": sha256(proc.stdout.encode()).hexdigest(),
                }
    return records


def main():
    oracles = [(evaluate(case, LEFT_FIRST), evaluate(case, RIGHT_FIRST)) for case in CASES]
    counts = Counter()
    witnesses = {}
    for case, (left, right) in zip(CASES, oracles, strict=True):
        counts["distinct_full_observation"] += left != right
        counts["distinct_terminal_and_cell"] += left[:3] != right[:3]
        counts["distinct_trace_only"] += left[:3] == right[:3] and left[3:] != right[3:]
        counts["distinct_failure_stage"] += left[0] == right[0] == "error" and left[1] != right[1]
        if left[:3] == right[:3] and left != right:
            witnesses.setdefault("trace_only", [case, left, right])
        if left[0] == right[0] == "error" and left[1] != right[1]:
            witnesses.setdefault("failure_stage", [case, left, right])
    print(json.dumps({
        "schema": "llmlang-call-evaluation/1", "python": platform.python_version(),
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "call.cc", "call.rs", "Order.lean", "axioms.txt")},
        "cases": len(CASES), "counts": counts, "witnesses": witnesses, "native": native(oracles),
    }, indent=2))


if __name__ == "__main__":
    main()
