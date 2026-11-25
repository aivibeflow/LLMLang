#!/usr/bin/env python3
"""Verify cache byte lifetimes across controlled native maintenance schedules."""

import argparse
from collections import Counter
from contextlib import ExitStack
import fcntl
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory

EXPECTED = b"archived compiler artifact\n"
OTHER = b"other bytes used by a fixture control\n"
ADDRESS = sha256(EXPECTED).hexdigest()
POLICIES = ("pathname", "descriptor", "snapshot", "revalidate", "lease")
EDITS = ("unchanged", "evict", "replace-identical", "replace-other", "rewrite-in-place")


def maintenance(root, edit):
    blob = root / "artifact"
    with (root / "lease").open("rb") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return "deferred"
        if edit == "evict":
            blob.unlink()
        elif edit in ("replace-identical", "replace-other"):
            new = root / "replacement"
            new.write_bytes(EXPECTED if edit == "replace-identical" else OTHER)
            new.replace(blob)
        elif edit == "rewrite-in-place":
            blob.write_bytes(OTHER)
        return "applied"


def run_maintenance(root, edit):
    return subprocess.check_output(
        [sys.executable, "-B", str(Path(__file__).resolve()), "--maintain", edit, str(root)],
        text=True, timeout=30, cwd=root,
    ).strip()


def check(root, policy, edit, initial):
    blob = root / "artifact"
    (root / "lease").touch()
    if initial != "missing":
        blob.write_bytes(EXPECTED if initial == "valid" else OTHER)

    with ExitStack() as opened:
        if policy == "lease":
            lock = opened.enter_context((root / "lease").open("rb"))
            fcntl.flock(lock, fcntl.LOCK_SH)
        try:
            input_stream = opened.enter_context(blob.open("rb", buffering=0))
        except FileNotFoundError:
            return {"outcome": "missing-before-check"}
        verified = input_stream.read()
        if sha256(verified).hexdigest() != ADDRESS:
            return {"outcome": "failed-initial-integrity"}
        edit_state = run_maintenance(root, edit)
        try:
            if policy == "snapshot":
                delivered = verified
            elif policy in ("descriptor", "lease"):
                input_stream.seek(0)
                delivered = input_stream.read()
            else:
                delivered = blob.read_bytes()
        except FileNotFoundError:
            return {"outcome": "missing-after-check", "maintenance": edit_state}
        observed = sha256(delivered).hexdigest()
        outcome = "exact" if observed == ADDRESS else "wrong-bytes"
        if policy == "revalidate" and outcome == "wrong-bytes":
            outcome = "failed-final-integrity"

    result = {"outcome": outcome, "maintenance": edit_state, "observed_sha256": observed}
    if edit_state == "deferred":
        result["maintenance_after_reader_release"] = run_maintenance(root, edit)
    return result


def expected_valid(policy, edit):
    if policy in ("snapshot", "lease") or edit in ("unchanged", "replace-identical"):
        return "exact"
    if policy == "descriptor" and edit in ("evict", "replace-other"):
        return "exact"
    if edit == "evict":
        return "missing-after-check"
    if policy == "revalidate":
        return "failed-final-integrity"
    return "wrong-bytes"


def compare():
    rows, counts = [], {policy: Counter() for policy in POLICIES}
    schedules = [("valid", edit) for edit in EDITS] + [("corrupt", "unchanged"), ("missing", "unchanged")]
    with TemporaryDirectory(prefix="llmlang-artifact-lifetime-") as directory:
        root = Path(directory)
        filesystem = subprocess.check_output(["stat", "-f", "-c", "%T", root], text=True).strip()
        for policy in POLICIES:
            for initial, edit in schedules:
                work = root / f"{policy}-{initial}-{edit}"
                work.mkdir()
                observation = check(work, policy, edit, initial)
                if initial == "valid":
                    expected = expected_valid(policy, edit)
                else:
                    expected = "missing-before-check" if initial == "missing" else "failed-initial-integrity"
                if observation["outcome"] != expected:
                    raise AssertionError((policy, initial, edit, observation))
                if initial == "valid" and policy == "lease" and (
                    observation["maintenance"], observation.get("maintenance_after_reader_release"),
                ) != ("deferred", "applied"):
                    raise AssertionError("The shared lease did not coordinate native maintenance")
                counts[policy][observation["outcome"]] += 1
                rows.append({"policy": policy, "initial": initial, "edit": edit, **observation})
    return {
        "schema": "llmlang-cache-artifact-lifetime/1", "python": platform.python_version(),
        "host": {"kernel": platform.release(), "machine": platform.machine(), "filesystem": filesystem},
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(), "expected_artifact_sha256": ADDRESS,
        "cases": rows, "counts": counts,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maintain", choices=EDITS)
    parser.add_argument("root", nargs="?", type=Path)
    args = parser.parse_args()
    if args.maintain is not None:
        print(maintenance(args.root, args.maintain))
    else:
        print(json.dumps(compare(), indent=2))
