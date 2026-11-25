#!/usr/bin/env python3
"""Kernel-check the worker model and exact guarded native schedule projections."""

import argparse
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
NATIVE = HERE.parents[2] / "language-design" / "RT-01" / "RESOURCE-WORKER-01"
PINNED_NATIVE = "5d77fb9ebff6a0ea83c2e1cc5f83acaea192c7a9066b46215b95e721c011d7cb"
LEAN_REVISION = "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9"


def digest(data):
    return sha256(data).hexdigest()


def lean_call(lean, directory, *arguments, check=True):
    return subprocess.run([lean, "-DwarningAsError=true", *arguments], cwd=directory, text=True,
                          capture_output=True, check=check, timeout=45,
                          env={**os.environ, "LEAN_PATH": str(directory)})


def audit(lines, prefix):
    results = {}
    for line in lines:
        row = re.fullmatch(rf"'{re.escape(prefix)}(\w+)' depends on axioms: \[(.*)\]", line)
        assert row, line
        theorem, entries = row.groups()
        assert theorem not in results
        axioms = entries.split(", ")
        assert set(axioms) <= {"propext", "Quot.sound"}
        results[theorem] = axioms
    return results


def bool_literal(value):
    return "true" if value else "false"


def lean_list(values):
    return "[" + ", ".join(values) + "]"


def string_list(values):
    return lean_list(json.dumps(value) for value in values)


def replay_code(rows, masks):
    chunks = ["import Worker", "open Worker"]
    computed = []
    expected = []
    for index, row in enumerate(rows):
        mask = masks[row["case"]]
        requests = []
        events = []
        for signal in row["events"]:
            target = signal["task"]
            operation = signal["command"]
            request = f".write {bool_literal(not (mask & (1 << target)))}" if operation == "write" else f".{operation}"
            requests.append(f"({bool_literal(target == 1)}, {request})")
            events.append(f'({json.dumps(signal["event"])}, {json.dumps(signal["open_handles"])}, '
                          f'{bool_literal(signal["released"])})')
        outcomes, effects = row["observed"]
        expression = f"replay (.idle, .idle) {lean_list(requests)}"
        literal = f"({lean_list(events)}, ({string_list(outcomes)}, {string_list(effects)}))"
        computed.append(f"({expression})")
        encoded_events = [[signal["event"], [signal["open_handles"], signal["released"]]]
                          for signal in row["events"]]
        expected.append([encoded_events, [outcomes, effects]])
        chunks.append(f"theorem checkedArchive{index} : {expression} = {literal} := by rfl")
        chunks.append(f"#print axioms checkedArchive{index}")
    chunks.append(f"#eval IO.println (Lean.Json.compress (Lean.toJson {lean_list(computed)}))")
    return "\n".join(chunks) + "\n", expected


def run(lean, native, directory):
    revision = subprocess.check_output([lean, "--version"], text=True).strip()
    assert LEAN_REVISION in revision
    proof = HERE / "Worker.lean"
    kernel = lean_call(lean, directory, f"--root={HERE}", "-o", str(directory / "Worker.olean"), str(proof))
    axioms = audit(kernel.stdout.splitlines(), "Worker.")
    assert len(axioms) == 12
    data = (native / "evidence.json").read_bytes()
    assert digest(data) == PINNED_NATIVE
    evidence = json.loads(data)
    for filename, expected in evidence["source_sha256"].items():
        assert digest((native / filename).read_bytes()) == expected
    spec = importlib.util.spec_from_file_location("native_worker_schedules", native / "run.py")
    schedule = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(schedule)
    masks = {name: row[0] for name, row in schedule.SCENARIOS.items()}
    guarded = [row for row in evidence["observations"] if row["policy"] == "guarded"]
    assert set(masks) == {row["case"] for row in guarded}
    emitted, expected = replay_code(guarded, masks)
    replay = directory / "Replay.lean"
    replay.write_text(emitted, encoding="utf-8")
    result = lean_call(lean, directory, str(replay)).stdout.splitlines()
    checked_archive = audit(result[:-1], "checkedArchive")
    assert len(checked_archive) == len(guarded)
    assert json.loads(result[-1]) == expected
    negative = directory / "Late.lean"
    negative.write_text("""import Worker
open Worker
example : (step (.known .ok) .cancel).phase = .revoked true := by rfl
""", encoding="utf-8")
    refused = lean_call(lean, directory, str(negative), check=False)
    assert refused.returncode == 1 and "not definitionally equal" in (refused.stdout + refused.stderr).lower()
    return {
        "schema": "llmlang-rt32-worker-cancel/1", "python": platform.python_version(), "lean": revision,
        "lean_source_sha256": digest(proof.read_bytes()), "runner_source_sha256": digest(Path(__file__).read_bytes()),
        "generated_replay_sha256": digest(emitted.encode()), "native_archive_sha256": PINNED_NATIVE,
        "generic_and_counterexample_axioms": axioms, "archive_equalities": checked_archive,
        "guarded_schedules": len(guarded), "guarded_steps": sum(len(row["events"]) for row in guarded),
        "guarded_terminal_outcomes": 2 * len(guarded),
        "native_host_configurations": evidence["configurations"],
        "incorrect_late_cancellation_proof": "rejected",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True)
    parser.add_argument("--native-dir", type=Path, default=NATIVE)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-rt32-worker-") as scratch:
        outcome = run(args.lean, args.native_dir.resolve(), Path(scratch))
    print(json.dumps(outcome, indent=2))
