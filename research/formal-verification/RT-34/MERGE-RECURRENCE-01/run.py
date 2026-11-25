#!/usr/bin/env python3
"""Compare the kernel-checked divide-and-conquer model with sorted native outputs."""

import argparse
from collections import Counter
from functools import cache
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
SIZES = (*range(97), 127, 128, 129, 255, 256, 257)
SHAPES = ("ascending", "descending", "duplicates", "alternating")
LEAN_REVISION = "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9"


def sorted_ranks_witness(values):
    """Place odd ranks left and even ranks right at each recursive split."""
    if len(values) < 2:
        return values
    return sorted_ranks_witness(values[1::2]) + sorted_ranks_witness(values[::2])


def input_values(size, shape):
    if shape == "ascending":
        return list(range(size))
    if shape == "descending":
        return list(range(size - 1, -1, -1))
    if shape == "duplicates":
        return [(3 * position + 1) % 5 for position in range(size)]
    return sorted_ranks_witness(list(range(size)))


def oracle(size):
    sizes = [size]
    writes = 0
    while sizes:
        current = sizes.pop()
        if current < 2:
            continue
        writes += current
        smaller = current // 2
        sizes.extend((smaller, current - smaller))
    return writes, writes - max(0, size - 1)


@cache
def equal_halves(size):
    if size < 2:
        return 0
    return size + 2 * equal_halves(size // 2)


def command(arguments, cwd=None, *, data=None, env=None):
    completed = subprocess.run(arguments, cwd=cwd, env=env, input=data, capture_output=True,
                               text=True, timeout=60, check=False)
    if completed.returncode or completed.stderr:
        raise RuntimeError(completed.stdout + completed.stderr)
    return completed.stdout


def generated_lean():
    sizes = ", ".join(map(str, SIZES))
    return f"""\
import MergeCost

def main : IO Unit := do
  for n in ([{sizes}] : List Nat) do
    let (writes, comparisons) := MergeCost.work n
    IO.println s!"{{n}} {{writes}} {{comparisons}}"
"""


def audit(output):
    pattern = re.compile(r"^'([^']+)' (?:does not depend on any axioms|depends on axioms: \[(.*)\])$")
    report = {}
    for line in output.splitlines():
        match = pattern.fullmatch(line)
        if match is None:
            raise ValueError(f"Unexpected Lean output {line!r}")
        name, axioms = match.groups()
        report[name] = [] if axioms is None else axioms.split(", ")
    assert len(report) == 7
    assert all(set(names) <= {"propext", "Classical.choice", "Quot.sound"} for names in report.values())
    return report


def simulate(compiler, lean, cases):
    source = generated_lean()
    lines = []
    for number, (_, values, invalid) in enumerate(cases):
        suffix = " ".join(map(str, values))
        lines.append(f"{number} {len(values)} {int(invalid)} {suffix}\n")
    data = "".join(lines)

    with TemporaryDirectory(prefix="llmlang-merge-recurrence-") as temporary:
        root = Path(temporary)
        shutil.copy(HERE / "MergeCost.lean", root / "MergeCost.lean")
        (root / "Counts.lean").write_text(source, encoding="utf-8")
        env = {**os.environ, "LEAN_PATH": str(root)}
        marker = [lean, "-DwarningAsError=true"]
        report = audit(command([*marker, "-o", "MergeCost.olean", "MergeCost.lean"], root, env=env))
        reductions = command([*marker, "--run", "Counts.lean"], root, env=env)
        actual = [tuple(map(int, line.split())) for line in reductions.splitlines()]
        assert actual == [(size, *oracle(size)) for size in SIZES]

        runs = []
        levels = ("0", "3")
        for value in levels:
            command([compiler, "-std=c17", "-Wall", "-Wextra", "-Werror", f"-O{value}",
                     str(HERE / "merge.c"), "-o", "merge"], root)
            runs.append(command(["./merge"], root, data=data))
        assert runs[0] == runs[1]
    return report, levels, runs[0], source


def digest(value):
    return sha256(value).hexdigest()


def replay(compiler, lean):
    revision = command([lean, "--version"]).strip()
    if LEAN_REVISION not in revision:
        raise ValueError("Expected pinned Lean 4.36.0")

    cases = [(shape, input_values(size, shape), False) for shape in SHAPES for size in SIZES]
    cases.extend(("bad_split", input_values(size, "ascending"), True) for size in (0, 1, 2, 3, 16))
    report, optimizations, raw, source = simulate(compiler, lean, cases)
    stats = {name: Counter(cases=0, exact_comparison_bound=0, loose_comparison_bound=0,
                           equal_halves_undercounts=0) for name in SHAPES}
    observations = []
    for number, ((shape, values, invalid), line) in enumerate(zip(cases, raw.splitlines(), strict=True)):
        index, accepted, writes, copyback, comparisons, *sorted_values = map(int, line.split())
        size = len(values)
        assert number == index
        if invalid:
            assert bool(accepted) == (size < 2)
            assert writes == copyback == comparisons == 0 and sorted_values == values
        else:
            assert accepted == 1 and sorted_values == sorted(values)
            expected_writes, limit = oracle(size)
            assert writes == copyback == expected_writes and comparisons <= limit
            if shape == "alternating":
                assert comparisons == limit
            if size > 0 and size & (size - 1) == 0:
                assert writes == size * (size.bit_length() - 1)
            row = stats[shape]
            row["cases"] += 1
            row["exact_comparison_bound"] += comparisons == limit
            row["loose_comparison_bound"] += comparisons < limit
            row["equal_halves_undercounts"] += equal_halves(size) < writes
        observations.append({
            "shape": shape, "size": size, "accepted": bool(accepted),
            "output_writes": writes, "copyback_writes": copyback, "comparisons": comparisons,
            "comparison_bound": oracle(size)[1],
        })

    return {
        "schema": "llmlang-merge-recurrence/1", "lean": revision,
        "compiler": command([compiler, "--version"]).splitlines()[0],
        "python": platform.python_version(), "theorems": report, "gcc_levels": optimizations,
        "source_sha256": {name: digest((HERE / name).read_bytes())
                          for name in ("MergeCost.lean", "merge.c", "run.py")},
        "generated_probe_sha256": digest(source.encode()),
        "native_output_sha256": digest(raw.encode()),
        "native_observations": len(cases) * len(optimizations),
        "lean_recurrence_observations": len(SIZES), "profiles": stats,
        "observations": observations,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--lean", default="lean")
    options = parser.parse_args()
    results = replay(options.cc, options.lean)
    rows = results.pop("observations")
    print(json.dumps(results, indent=2).removesuffix("\n}") + ',\n  "observations": [')
    print(",\n".join("    " + json.dumps(row) for row in rows))
    print("  ]\n}")
