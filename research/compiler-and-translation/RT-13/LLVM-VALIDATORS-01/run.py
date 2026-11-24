#!/usr/bin/env python3
"""Compare one LLVM fixture in Alive2 translation validation and Vellvm execution."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
CASES = {
    "identity": ("valid", 0, "Transformation seems to be correct!", 4),
    "wrap": ("refuted", 0, "ERROR: Target is more poisonous than source", 4),
    "alias": ("refuted", 0, "ERROR: Value mismatch", 4),
    "atomic": ("unsupported", 1, "ERROR: Unsupported instruction:", 4),
    "fence": ("unsupported", 1, "ERROR: Unsupported instruction:", 2),
}


def execute(*arguments):
    command = list(map(str, arguments))
    return subprocess.run(command, text=True, capture_output=True, timeout=90)


def require_vellvm(program, source, expected, *, failed=0):
    run = execute(program, "-test-file", source)
    summary = re.search(r"^Passed: (\d+)/(\d+)\s+Failed: (\d+)/(\d+)$", run.stdout, re.MULTILINE)
    if (summary is None or tuple(map(int, summary.groups())) != (expected - failed, expected, failed, expected)
            or bool(run.returncode) != bool(failed)):
        raise ValueError(f"Vellvm result for {source.name}: exit {run.returncode}\n{run.stdout}\n{run.stderr}")
    return {"passed": expected - failed, "failed": failed, "exit_code": run.returncode}


def replay(args):
    exact = {}
    digests = {}
    with TemporaryDirectory(prefix="llmlang-rt13-refiners-") as directory:
        work = Path(directory)
        for name, (verdict, expected_exit, marker, assertions) in CASES.items():
            source = HERE / f"{name}.ll"
            bitcode = work / f"{name}.bc"
            assembled = execute(args.asm, source, "-o", bitcode)
            verified = execute(args.opt, "-passes=verify", "-disable-output", bitcode)
            if assembled.returncode or verified.returncode:
                raise ValueError(f"LLVM rejected {name}: {assembled.stderr!r} {verified.stderr!r}")
            result = execute(args.alive, source)
            text = result.stdout + result.stderr
            if text.count(marker) != 1 or result.returncode != expected_exit:
                raise ValueError(f"Unexpected Alive2 {name} result ({result.returncode}): {text}")
            if name == "wrap" and not all(x in text for x in ("#x7f (127)", "#x80 (128, -128)", "Target value: poison")):
                raise ValueError("Alive2 lost the signed-boundary witness")
            if name == "alias" and not all(x in text for x in ("Source value: #x09 (9)", "Target value: #x07 (7)")):
                raise ValueError("Alive2 lost the aliased pointer result witness")
            if name in ("atomic", "fence") and ("atomicrmw add" if name == "atomic" else "fence acquire") not in text:
                raise ValueError(f"Unexpected unsupported operation in {name}")
            exact[name] = {"alive2": verdict, "alive2_exit_code": result.returncode,
                           "vellvm": require_vellvm(args.vellvm, source, assertions)}
            digests[source.name] = sha256(source.read_bytes()).hexdigest()
        mutant = work / "wrong-expectation.ll"
        text = (HERE / "identity.ll").read_text(encoding="utf-8")
        mutant.write_text(text.replace("; ASSERT EQ: i8 0 = call i8 @src(i8 0)",
                                       "; ASSERT EQ: i8 1 = call i8 @src(i8 0)"), encoding="utf-8")
        failed = require_vellvm(args.vellvm, mutant, 4, failed=1)
    digests["run.py"] = sha256(Path(__file__).read_bytes()).hexdigest()
    return {"schema": "llmlang-rt13-alive2-vellvm-crosscheck-v1",
            "llvm": execute(args.opt, "--version").stdout.splitlines()[0],
            "alive2_revision": "84041960f183aec74d740ff881c95a4ce5234d3d",
            "vellvm_revision": "7f0610c38d829b79bf6e867edf410c9e6f928f98",
            "inputs_sha256": digests, "cases": exact, "changed_vellvm_assertion": failed}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alive", type=Path, required=True)
    parser.add_argument("--vellvm", type=Path, required=True)
    parser.add_argument("--asm", default="llvm-as-19")
    parser.add_argument("--opt", default="opt-19")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(replay(args), indent=2) + "\n", encoding="utf-8")
