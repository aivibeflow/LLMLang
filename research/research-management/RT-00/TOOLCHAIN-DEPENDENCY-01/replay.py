#!/usr/bin/env python3
"""Replay the pinned Toolchain evidence used to revise five dependency edges."""
import argparse
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile


BASE = "2805481d1f9fb9d013c464070359c62513be3b5d"
ROOT = "research/toolchain-and-collaboration"
REGISTER = "research/research-management/RESEARCH-DEPENDENCY-MAP.md"
EDGES = ("DEP-047", "DEP-048", "DEP-058", "DEP-263", "DEP-264")
ENV = {**os.environ, "LC_ALL": "C", "TZ": "UTC", "PYTHONHASHSEED": "1"}


def run(command, cwd, timeout=120):
    return subprocess.run(command, cwd=cwd, env=ENV, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout).stdout


def git(top, *arguments):
    return run(["git", *arguments], top)


def prepare(top, archive):
    source = git(top, "archive", BASE, ROOT, "research/PROTOTYPES", REGISTER)
    with tarfile.open(fileobj=BytesIO(source), mode="r:") as content:
        content.extractall(archive, filter="data")


def sha(data):
    return sha256(data).hexdigest()


def replay(top, archive, executable, expected_file, arguments=(), *, stdout=False):
    expected = (archive / expected_file).read_bytes()
    command = [sys.executable, "-B", archive / executable, *arguments]
    destination = archive / "replay.json"
    actual = run(command if stdout else [*command, destination], archive)
    if not stdout:
        actual = destination.read_bytes()
        destination.unlink()
    assert expected == actual, (str(executable), sha(expected), sha(actual))
    return json.loads(actual), {
        "runner_blob": git(top, "rev-parse", f"{BASE}:{executable}").decode().strip(),
        "expected_blob": git(top, "rev-parse", f"{BASE}:{expected_file}").decode().strip(),
        "verified_sha256": sha(actual),
    }


def summarize(data):
    interchange = data["interchange"]
    authority = data["authority"]
    coherent = data["coherent"]
    remote = data["two-repositories"]
    faults = data["faults"]
    contract = data["contract"]["outcomes"]
    cip = data["cip"]
    values = {
        "pinned_leased_exports": interchange["coherent_leased_reads"],
        "checkout_edits_missed_by_stat": interchange["stat_missed_checkout"],
        "authority_schedules": authority["scenarios"],
        "unfenced_unauthorized_effects": authority["metrics"]["split_fresh"]["unauthorized_effect"],
        "unfenced_unauthorized_disclosures": authority["metrics"]["split_fresh"]["unauthorized_disclosure"],
        "fenced_unauthorized_effects": authority["metrics"]["split_fenced"]["unauthorized_effect"],
        "fenced_unauthorized_disclosures": authority["metrics"]["split_fenced"]["unauthorized_disclosure"],
        "cip_completion_cases": len(cip["cases"]),
        "cip_distinct_receipt_commits": len({row["git_commit"] for row in cip["cases"]}),
        "native_ref_schedule_count": sum(len(schedules) for profile in coherent["profiles"]
                                         for schedules in profile["schedules"].values()),
        "native_remote_schedule_count": sum(map(len, remote["ref_storage_outcomes"].values())),
        "fault_visibility_by_backend": {
            backend: [" ".join(row["visible_after_exit"]) for row in rows if row["exit"] != 0]
            for backend, rows in faults["profiles"].items()
        },
        "contract_distinct_states": contract["candidate"]["distinct_states"],
        "contract_controls": sum("violated" in row for row in contract.values()),
    }
    assert values["pinned_leased_exports"] == 21 and values["checkout_edits_missed_by_stat"] == 18
    assert (values["authority_schedules"], values["unfenced_unauthorized_effects"],
            values["unfenced_unauthorized_disclosures"]) == (48, 2, 1)
    assert (values["fenced_unauthorized_effects"], values["fenced_unauthorized_disclosures"]) == (0, 0)
    assert values["cip_completion_cases"] == 7 and values["cip_distinct_receipt_commits"] == 1
    assert values["native_ref_schedule_count"] == 308 and values["native_remote_schedule_count"] == 24
    assert values["fault_visibility_by_backend"] == {
        "files": ["old old", "old old", "old old", "new old"],
        "reftable": ["old old"] * 6 + ["new new"] * 3,
    }
    assert values["contract_distinct_states"] == 4032 and values["contract_controls"] == 7
    return values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tlc", type=lambda value: Path(value).resolve(), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    top = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").decode().strip())
    cases = {
        "interchange": ("RT-19/INTERCHANGE-BOUNDARY-01", "check.py", "evidence.json", (), True),
        "authority": ("RT-19/RECOVERY-AUTHORITY-01", "run.py", "evidence.json", (), True),
        "coherent": ("RT-19/COHERENT-MULTIREF-01", "run.py", "observations.json", ("--out",), False),
        "two-repositories": ("RT-19/TWO-REMOTE-PUBLICATION-01", "run.py", "observations.json", ("--out",), False),
        "faults": ("RT-19/GIT-REF-FAULTS-01", "run.py", "observations.json", ("--out",), False),
        "contract": ("RT-19/PUBLICATION-CONTRACT-01", "run.py", "observations.json",
                     ("--tlc", args.tlc, "--out"), False),
        "cip": ("RT-20/COMPLETION-OUTBOX-01", "run.py", "evidence.json", (), False),
    }
    with tempfile.TemporaryDirectory(prefix="rt00-toolchain-edges-") as scratch:
        archive = Path(scratch)
        prepare(top, archive)
        pins, evidence = {}, {}
        for label, (path, executable, expected, arguments, stdout) in cases.items():
            fixture = Path(ROOT, path)
            evidence[label], pins[label] = replay(top, archive, fixture / executable,
                                                   fixture / expected, arguments, stdout=stdout)
        map_rows = (archive / REGISTER).read_text().splitlines()
        baseline = {edge: [row for row in map_rows if row.startswith(f"| {edge} |")]
                    for edge in EDGES}
        assert all(len(found) == 1 for found in baseline.values())
        counts = summarize(evidence)
    ledger = {"baseline": BASE, "baseline_rows": {edge: found[0] for edge, found in baseline.items()},
              "pins": pins, "claims": counts}
    args.out.write_text(json.dumps(ledger, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
