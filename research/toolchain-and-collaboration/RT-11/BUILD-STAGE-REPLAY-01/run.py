#!/usr/bin/env python3
"""Replay the five pinned build stages and compare exact archived invariants."""

import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path("research/toolchain-and-collaboration/RT-11/COMPILE-CACHE-TIMINGS-01")
BASELINE = "0f4d06770500a9482cd175c67afe0dc620d49a5c"


def execute(args):
    return subprocess.run(args, cwd=ROOT, capture_output=True, check=True, timeout=120).stdout


def archive(name):
    return execute(["git", "show", f"{BASELINE}:{SOURCE / name}"])


def group(record):
    rows = {(row["stage"], row["trial"], row["method"]): row for row in record["samples"]}
    if len(rows) != len(record["samples"]):
        raise AssertionError("Repeated stage/trial/method")
    return rows


def validate(published, fresh):
    for field in ("schema", "order_seed", "translation_units", "groups", "compile_flags", "input_shape",
                  "toolchain", "source_sha256"):
        if fresh[field] != published[field]:
            raise AssertionError((field, fresh[field], published[field]))
    prior = group(published)
    observed = group(fresh)
    durations = defaultdict(lambda: defaultdict(list))
    counts = {}
    for key, row in observed.items():
        stage, trial, method = key
        baseline = prior[key]
        for field in ("order", "compiler_invocations", "cache_hits", "manifest_sha256"):
            if row[field] != baseline[field]:
                raise AssertionError((stage, trial, method, field, row[field], baseline[field]))
        durations[stage][method].append(row["elapsed_ns"])
        counts.setdefault(stage, {})[method] = {
            "compiled": row["compiler_invocations"], "hits": row["cache_hits"],
            "manifest_sha256": row["manifest_sha256"],
        }
        if row["elapsed_ns"] <= 0:
            raise AssertionError(row)
    if len(observed) != len(fresh["input_shape"]) * fresh["repetitions"] * 3:
        raise AssertionError("Incomplete coverage of methods and stages")
    return {
        "exact_checked_rows": len(observed), "complete_blocks": len(observed) // 3,
        "exact_by_stage_and_method": counts,
        "fresh_median_ns": {stage: {method: median(values) for method, values in methods.items()}
                            for stage, methods in durations.items()},
    }


def run(clang, make, trials):
    engine = archive("run.py")
    ledger = archive("evidence.json")
    expected = json.loads(ledger)
    if sha256(engine).hexdigest() != expected["source_sha256"]:
        raise AssertionError("Archived runner and evidence disagree")
    if not 1 <= trials <= expected["repetitions"]:
        raise ValueError("Trial count has to fit inside the archived timing blocks")
    with TemporaryDirectory(prefix="llmlang-five-stage-replay-") as temp:
        path = Path(temp) / "run.py"
        path.write_bytes(engine)
        fresh = json.loads(execute([sys.executable, "-B", path, "--clang", clang.resolve(), "--make",
                                   make.resolve(), "--trials", str(trials), "--seed", str(expected["order_seed"])]))
    return {
        "schema": "llmlang-build-stage-replay/1", "baseline": BASELINE,
        "archive_evidence_sha256": sha256(ledger).hexdigest(),
        "archive_source_sha256": sha256(engine).hexdigest(),
        "verification": validate(expected, fresh), "fresh_observations": fresh,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", type=Path, required=True)
    parser.add_argument("--make", type=Path, default=Path("/usr/bin/make"))
    parser.add_argument("--trials", type=int, default=3)
    args = parser.parse_args()
    print(json.dumps(run(args.clang, args.make, args.trials), indent=2))
