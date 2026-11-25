"""Replay the bounded RT-19 and RT-23 studies from the repository root."""

import hashlib
import json
import os
import platform
import sqlite3
import subprocess
import tempfile
from pathlib import Path

BASELINE = "c03e64fcc3a3b195ae0922a678b6aa39743b552e"
ROOT = Path("research/toolchain-and-collaboration")
FIXTURES = (
    ("RT-19/sqlite-git-crash-recovery", "results.json", True),
    ("RT-19/EXTERNAL-RECEIPT-RECOVERY-01", "evidence.json", False),
    ("RT-19/MUTABLE-LOG-RECOVERY-01", "evidence.json", False),
    ("RT-19/RECOVERY-AUTHORITY-01", "evidence.json", False),
    ("RT-23/SINGLE-JOURNAL-REF-01", "evidence.json", True),
    ("RT-23/INDEXED-JOURNAL-RECOVERY-01", "evidence.json", False),
    ("RT-23/PINNED-GIT-RETENTION-01", "evidence.json", True),
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def version(*args):
    return subprocess.check_output(args, text=True).splitlines()[0]


def pinned_bytes(path):
    expected = subprocess.check_output(["git", "show", f"{BASELINE}:{path}"])
    if path.read_bytes() != expected:
        raise RuntimeError(f"{path} differs from {BASELINE}")
    return expected


def main():
    environment = os.environ | {"LC_ALL": "C", "PYTHONHASHSEED": "1"}
    observations = {}
    with tempfile.TemporaryDirectory(prefix="llmlang-recovery-replay-") as temporary:
        output = Path(temporary) / "result.json"
        for directory, ledger_name, use_output_flag in FIXTURES:
            runner = ROOT / directory / "run.py"
            ledger = ROOT / directory / ledger_name
            source = pinned_bytes(runner)
            archived = pinned_bytes(ledger)
            command = ["python3", "-B", str(runner)]
            if use_output_flag:
                subprocess.run(
                    command + ["--output", str(output)], check=True,
                    env=environment, timeout=180,
                )
                observed = output.read_bytes()
                output.unlink()
            else:
                observed = subprocess.check_output(command, env=environment, timeout=180)
            if observed != archived:
                raise RuntimeError(
                    f"{directory} generated {digest(observed)}; archive has {digest(archived)}"
                )
            observations[directory] = {
                "runner_sha256": digest(source),
                "ledger_path": str(ledger),
                "archived_sha256": digest(archived),
                "observed_sha256": digest(observed),
                "byte_equal": True,
            }
        filesystem = version("stat", "-f", "-c", "%T", temporary)
    print(json.dumps({
        "baseline": BASELINE,
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "git": version("git", "--version"),
        "gcc": version("gcc", "--version"),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "temporary_filesystem": filesystem,
        "locale": environment["LC_ALL"],
        "python_hash_seed": environment["PYTHONHASHSEED"],
        "replays": observations,
    }, indent=2))


if __name__ == "__main__":
    main()
