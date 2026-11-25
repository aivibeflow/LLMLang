#!/usr/bin/env python3
"""Replay five observation studies from an exact published research/all tree."""

from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from tarfile import open as tar_open
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[4]
BASELINE = "3eb5482a04232a129e6f71496587e2dd3cf7872d"
FORMAL = Path("research/formal-verification/RT-07")
COMPILER = Path("research/compiler-and-translation/RT-13")
PROTOTYPE = Path("research/PROTOTYPES/RT-04-01")
TOOLS_ENV = {**os.environ, "LC_ALL": "C", "PYTHONHASHSEED": "1"}


def execute(args, root):
    result = subprocess.run(args, cwd=root, env=TOOLS_ENV, check=True,
                            capture_output=True, timeout=45)
    return result.stdout


def replay():
    lean = shutil.which("lean")
    if lean is None:
        raise RuntimeError("The pinned Lean executable must be on PATH")
    cases = (
        ("executable_reference", FORMAL / "STATE-RESULT-REFERENCE-01", "validate.py", None),
        ("dead_store", FORMAL / "DEAD-STORE-BOUNDARY-01", "run.py", "Store.lean"),
        ("partial_output", FORMAL / "PARTIAL-OUTPUT-01", "run.py", "Prefix.lean"),
        ("rewrite_mutation", COMPILER / "STATE-RESULT-MUTATIONS-01", "run.py", None),
        ("exact_swap", COMPILER / "WRITE-SWAP-VALIDATION-01", "run.py", None),
    )
    archive_paths = [path for _, path, _, _ in cases]
    archive_paths += [FORMAL / "THREE-SEMANTICS-01", PROTOTYPE / "rt03_reference.py",
                      PROTOTYPE / "rt03_smallstep.py"]
    archive_bytes = execute(["git", "archive", BASELINE, *archive_paths], ROOT)
    records = {}
    ledgers = {}
    with TemporaryDirectory(prefix="llmlang-observation-edge-") as directory:
        target = Path(directory)
        with tar_open(fileobj=BytesIO(archive_bytes)) as archive:
            archive.extractall(target, filter="data")
        for label, fixture, runner, proof in cases:
            record = {}
            if proof:
                theorem_output = execute([lean, "-DwarningAsError=true", fixture / proof], target)
                if theorem_output != (target / fixture / "axioms.txt").read_bytes():
                    raise AssertionError(f"Axiom ledger mismatch for {label}")
                record["axioms_sha256"] = sha256(theorem_output).hexdigest()
            command = [sys.executable, "-B", fixture / runner]
            if label == "exact_swap":
                command += ["--lean", lean]
            actual = execute(command, target)
            if actual != (target / fixture / "evidence.json").read_bytes():
                raise AssertionError(f"Evidence ledger mismatch for {label}")
            records[label] = {**record, "path": fixture.as_posix(),
                              "ledger_sha256": sha256(actual).hexdigest()}
            ledgers[label] = json.loads(actual)

    original = ledgers["executable_reference"]
    store = ledgers["dead_store"]
    output = ledgers["partial_output"]
    mutation = ledgers["rewrite_mutation"]["corpora"]["bounded_exhaustive"]
    swap = ledgers["exact_swap"]
    return {
        "schema": "llmlang-observation-edge-replay/1", "baseline": BASELINE,
        "tools": {
            "python": platform.python_version(),
            "git": execute(["git", "--version"], ROOT).decode().strip(),
            "lean": execute([lean, "--version"], ROOT).decode().strip(),
            "gcc": execute(["gcc", "--version"], ROOT).decode().splitlines()[0],
        },
        "replays": records,
        "edge_discriminators": {
            "reference_comparisons": original["comparisons"],
            "final_cell_false_store_admissions": store["guards"]["final_cells"]["false_admission"],
            "exact_store_guard_false_admissions": store["guards"]["exact_rule"]["false_admission"],
            "coalescing_call_trace_differences": output["counts"]["split_pairs_differing_in_calls"],
            "order_mismatches_hidden_by_multiset": (
                mutation["differences"]["exchange_write_order"]["complete"]
                - mutation["differences"]["exchange_write_order"]["event_multiset"]
            ),
            "overwritten_writes_hidden_by_result_and_cell": (
                mutation["differences"]["drop_overwritten_write"]["complete"]
                - mutation["differences"]["drop_overwritten_write"]["result_and_cell"]
            ),
            "swap_false_admissions_from_final_heap": swap["state_only_false_admissions"],
            "wrong_emitted_target_same_subject": (
                swap["wrong_target_control"]["source_target_receipt"]
                == swap["wrong_target_control"]["actual_target_receipt_key"]
            ),
        },
    }


if __name__ == "__main__":
    print(json.dumps(replay(), indent=2))
