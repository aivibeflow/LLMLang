#!/usr/bin/env python3
"""Kernel-check the extrema guard and compare every archived native policy vector."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
NATIVE = HERE.parents[2] / "semantic-representation" / "RT-05" / "NATIVE-F64-MINMAX-01"
NATIVE_DIGEST = "d6bb67b8007e34185cebfbecccf0c318dfda471b124084a5fb2f39899aab63e5"
LEAN_REVISION = "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9"
RULES = {"glibc": "propagateSignalingRight", "sse2": "unorderedRight", "rust": "preferNumberLeft",
         "node": "propagate", "python": "orderedLeft"}


def digest(data):
    return sha256(data).hexdigest()


def lean_call(lean, directory, *arguments):
    return subprocess.run([lean, "-DwarningAsError=true", *arguments], cwd=directory, capture_output=True,
                          text=True, timeout=75, env={**os.environ, "LEAN_PATH": str(directory)})


def audit(result, prefix):
    assert result.returncode == 0, result.stdout + result.stderr
    declarations = {}
    for line in result.stdout.splitlines():
        row = re.fullmatch(rf"'{re.escape(prefix)}([\w.]+)' depends on axioms: \[(.*)\]", line)
        if row:
            name, entries = row.groups()
            axioms = entries.split(", ")
        else:
            row = re.fullmatch(rf"'{re.escape(prefix)}([\w.]+)' does not depend on any axioms", line)
            assert row, line
            name, axioms = row[1], []
        assert name not in declarations and set(axioms) <= {"propext", "Classical.choice", "Quot.sound"}, line
        declarations[name] = axioms
    return declarations


def operand(bits):
    assert re.fullmatch(r"[0-9a-f]{16}", bits)
    return "0x" + bits


def normalized(bits):
    if int(bits, 16) & 0x7fffffffffffffff > 0x7ff0000000000000:
        return "7ff8000000000000"
    return bits


def expected_guard(row):
    a, b = row["operands"]
    numeric_results = {tuple(map(normalized, result)) for result in row["results"].values()}
    classification = [int(value, 16) & 0x7fffffffffffffff > 0x7ff0000000000000 for value in (a, b)]
    mixed_zero = {a, b} == {"0000000000000000", "8000000000000000"}
    expected = all(classification) or not any(classification) and not mixed_zero
    assert expected == (len(numeric_results) == 1)
    return expected


def replay_code(rows, first, stop):
    decls = ["import Extrema", "open F64Extrema", "set_option maxHeartbeats 1000000"]
    for index in range(first, stop):
        row = rows[index]
        left, right = map(operand, row["operands"])
        admitted = str(expected_guard(row)).lower()
        expression = ", ".join([f"agreementGuard {left} {right}",
                                *(f"evaluate .{rule} {left} {right}" for rule in RULES.values())])
        raw = [tuple(map(operand, row["results"][family])) for family in RULES]
        literal = ", ".join([admitted, *(f"(normalizeResult {lo}, normalizeResult {hi})" for lo, hi in raw)])
        decls.extend([f"theorem archiveCase{index} : ({expression}) = ({literal}) := by rfl",
                      f"#print axioms archiveCase{index}"])
    return "\n".join(decls) + "\n"


def check_archive(lean, directory, rows):
    sources = {}
    for first in range(0, len(rows), 64):
        path = directory / f"Replay{first}.lean"
        contents = replay_code(rows, first, min(first + 64, len(rows)))
        path.write_text(contents, encoding="utf-8")
        sources[path] = digest(contents.encode())

    def verify(path):
        return audit(lean_call(lean, directory, str(path)), "archiveCase")

    equalities = {}
    with ThreadPoolExecutor(max_workers=3) as workers:
        for result in workers.map(verify, sources):
            assert not set(equalities) & set(result)
            equalities.update(result)
    assert set(equalities) == {str(index) for index in range(len(rows))}
    return equalities, {path.name: source for path, source in sources.items()}


def run(lean, directory):
    version = subprocess.check_output([lean, "--version"], text=True).strip()
    assert LEAN_REVISION in version
    archive = (NATIVE / "evidence.json").read_bytes()
    assert digest(archive) == NATIVE_DIGEST
    data = json.loads(archive)
    for name, expected in data["sources"].items():
        assert digest((NATIVE / name).read_bytes()) == expected
    rows = data["observations"]
    assert len(rows) == data["ordered_pairs"] == 1024
    admitted = sum(map(expected_guard, rows))
    assert admitted == 518
    proof = HERE / "Extrema.lean"
    result = lean_call(lean, directory, f"--root={HERE}", "-o", str(directory / "Extrema.olean"), str(proof))
    theorems = audit(result, "F64Extrema.")
    assert len(theorems) == 9
    equalities, sources = check_archive(lean, directory, rows)
    wrong = directory / "Incorrect.lean"
    wrong.write_text("""import Extrema
open F64Extrema
example : evaluate .propagate positiveZero negativeZero =
    evaluate .preferNumberLeft positiveZero negativeZero := by rfl
""", encoding="utf-8")
    refused = lean_call(lean, directory, str(wrong))
    assert refused.returncode == 1 and "not definitionally equal" in (refused.stdout + refused.stderr).lower()
    return {"schema": "llmlang-rt32-f64-extrema-agreement-guard/1", "python": platform.python_version(), "lean": version,
            "sources": {name: digest((HERE / name).read_bytes()) for name in ("Extrema.lean", "run.py")},
            "native_archive_sha256": NATIVE_DIGEST, "archive_replay_sources_sha256": sources,
            "native_policy_map": RULES, "model_theorem_axioms": theorems, "archive_equalities": equalities,
            "guard_admitted_in_archive": admitted, "guard_refused_in_archive": len(rows) - admitted,
            "false_unguarded_substitution_proof": "rejected"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-rt32-extrema-") as scratch:
        print(json.dumps(run(args.lean, Path(scratch)), indent=2))
