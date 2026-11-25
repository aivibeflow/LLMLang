#!/usr/bin/env python3
"""Check actual Git ref visibility and recovery under targeted local syscall faults."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
NAMES = ("refs/llmlang/fixture/alpha", "refs/llmlang/fixture/beta")
ENV = {key: value for key, value in os.environ.items() if not key.startswith(("GIT_", "LD_", "FIXTURE_"))}
ENV.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            "GIT_AUTHOR_DATE": "2001-01-01T00:00:00+00:00",
            "GIT_COMMITTER_DATE": "2001-01-01T00:00:00+00:00", "LC_ALL": "C"})
CASES = {
    "files": [
        None,
        ("write", "beta-lock", 1),
        ("fsync", "beta-lock", 1),
        ("rename", "alpha-lock", 1),
        ("rename", "beta-lock", 1),
    ],
    "reftable": [
        None,
        ("write", "table-temp", 1),
        ("fsync", "table-temp", 1),
        ("rename", "table-temp", 1),
        ("write", "table-list-lock", 1),
        ("fsync", "table-list-lock", 1),
        ("rename", "table-list-lock", 1),
        ("write", "table-temp", 3),
        ("fsync", "table-list-lock", 2),
        ("rename", "table-list-lock", 2),
    ],
}


def git(root, *args, data=None, env=ENV, check=True):
    result = subprocess.run(["git", *args], cwd=root, env=env, input=data,
                            text=True, capture_output=True, timeout=15)
    if check:
        assert result.returncode == 0, (args, result.stdout, result.stderr)
    return result


def initialize(root, storage):
    root.mkdir()
    git(root, "init", "--quiet", "--bare", "--initial-branch=research/all", f"--ref-format={storage}")
    tree = git(root, "mktree", data="").stdout.strip()
    old = git(root, "commit-tree", tree, "-m", "old").stdout.strip()
    new = git(root, "commit-tree", tree, "-p", old, "-m", "new").stdout.strip()
    for ref in NAMES:
        git(root, "update-ref", ref, old)
    return old, new


def read_vector(root, old, new):
    candidates = {old: "old", new: "new"}
    return [candidates[git(root, "rev-parse", "--verify", ref).stdout.strip()] for ref in NAMES]


def transaction(root, old, new, *, env=ENV, policy="reference"):
    writes = [f"update {ref} {new} {old}" for ref in NAMES]
    data = "\n".join(["start", *writes, "prepare", "commit", ""])
    return git(root, "-c", f"core.fsync={policy}", "-c", "core.fsyncMethod=fsync",
               "update-ref", "--stdin", data=data, env=env, check=False)


def experiment(directory, library, storage, fault, policy="reference"):
    old, new = initialize(directory, storage)
    log_path = directory / "fault-operations.log"
    settings = {**ENV, "LD_PRELOAD": str(library), "FIXTURE_ROOT": str(directory),
                "FIXTURE_LOG": str(log_path)}
    if fault:
        op, role, occurrence = fault
        settings.update(FIXTURE_OPERATION=op, FIXTURE_ROLE=role,
                        FIXTURE_OCCURRENCE=str(occurrence))
    result = transaction(directory, old, new, env=settings, policy=policy)
    events = [line.split() for line in log_path.read_text().splitlines()]
    failures = [entry for entry in events if entry[2] == "failed"]
    if fault:
        assert failures == [[op, role, "failed"]], (storage, fault, events)
        assert result.returncode == 128, (storage, fault, result.returncode)
        assert sum(entry[:2] == [op, role] for entry in events[:events.index(failures[0]) + 1]) == occurrence
    else:
        assert not failures and result.returncode == 0
        assert any(entry[0] == "fsync" for entry in events) == (policy == "reference")
    actual = read_vector(directory, old, new)
    locks = sorted(path.relative_to(directory).as_posix() for path in directory.rglob("*.lock"))
    assert not locks
    if actual == ["old", "old"]:
        recovery = "retry-exact-old-vector"
        assert transaction(directory, old, new).returncode == 0
        assert read_vector(directory, old, new) == ["new", "new"]
    elif actual == ["new", "new"]:
        recovery = "observe-exact-visible-vector"
    else:
        recovery = "refuse-mixed-vector"
        assert transaction(directory, old, new).returncode != 0
        assert read_vector(directory, old, new) == actual
    messages = (result.stdout + result.stderr).replace(str(directory), "<repo>")
    messages = re.sub(r"0x[0-9a-f]{16}-0x[0-9a-f]{16}-[0-9a-f]{8}(?:\.temp\.[A-Za-z0-9]+)?",
                      "<table>", messages)
    return {"fault": fault, "policy": policy, "exit": result.returncode,
            "events": events, "visible_after_exit": actual, "remaining_locks": locks,
            "recovery": recovery, "reported": messages.strip().splitlines()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt19-git-faults-") as directory:
        root = Path(directory)
        library = root / "fault.so"
        subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC",
                        HERE / "fault.c", "-o", library], check=True)
        profiles = {}
        for storage, faults in CASES.items():
            outcomes = [experiment(root / f"{storage}-{index}", library, storage, fault)
                        for index, fault in enumerate(faults)]
            outcomes.append(experiment(root / f"{storage}-sync-disabled", library, storage, None, "none"))
            profiles[storage] = outcomes
        assert [row["recovery"] for row in profiles["files"]] == [
            "observe-exact-visible-vector", *["retry-exact-old-vector"] * 3,
            "refuse-mixed-vector", "observe-exact-visible-vector",
        ]
        assert [row["recovery"] for row in profiles["reftable"]] == [
            "observe-exact-visible-vector", *["retry-exact-old-vector"] * 6,
            *["observe-exact-visible-vector"] * 4,
        ]
        report = {"git": git(root, "--version").stdout.strip(), "profiles": profiles}
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
