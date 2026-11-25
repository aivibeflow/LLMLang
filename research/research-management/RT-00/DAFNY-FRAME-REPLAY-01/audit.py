"""Replay the exact tracked Dafny frame and native-history fixture."""

import argparse
from collections import Counter
from hashlib import file_digest, sha256
from itertools import product
import json
from math import factorial
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BASE = "32bf8da9b5b5e9794abd6077e4d253ba1c2be3a5"
FIXTURE = Path("research/formal-verification/RT-07/DAFNY-CONCURRENT-FRAME-HISTORY-01")
PACKAGE_HASH = "a46a9ff7cdd720f7955854c78e95df13f4cfe6b80691b05f8654fe19e8267179"


def sha(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def check_histories(ledger):
    admitted = Counter()
    cases = Counter()
    for row in ledger["histories"]:
        actors, base, events = row["actors"], row["base"], row["events"]
        positions = {event: index for index, event in enumerate(events)}
        assert set(positions) == set(range(2 * actors))
        assert all(positions[2 * actor] < positions[2 * actor + 1] for actor in range(actors))
        for route, outcome in row["routes"].items():
            cases[actors, route] += 1
            ranks = [reply - base - 1 for reply in outcome["replies"]]
            assert all(old + 1 == reply for old, reply in zip(
                outcome["prior_values"], outcome["replies"], strict=True
            ))
            rank_set_valid = set(ranks) == set(range(actors))
            precedence = all(ranks[left] < ranks[right]
                             for left, right in product(range(actors), repeat=2)
                             if positions[2 * left + 1] < positions[2 * right])
            expected = (sorted(range(actors), key=ranks.__getitem__)
                        if rank_set_valid and precedence and outcome["state"] == base + actors else None)
            assert expected == outcome["serial_witness"]
            admitted[actors, route] += expected is not None
    starts = len(ledger["base_values"])
    for actors in (2, 3):
        total = starts * factorial(2 * actors) // 2**actors
        assert cases[actors, "split"] == cases[actors, "rmw"] == total
        assert admitted[actors, "split"] == starts * factorial(actors)
        assert admitted[actors, "rmw"] == total
    return {"unique_history_rows": len(ledger["histories"]), "rank_oracle_comparisons": sum(cases.values()),
            "native_optimization_profiles": ledger["native_profiles"],
            "native_executions": sum(cases.values()) * len(ledger["native_profiles"])}


def replay(args, work):
    if sha(args.archive) != PACKAGE_HASH:
        raise ValueError("The upstream archive digest differs from the recorded release")
    git = ["git", "-C", str(REPO)]
    archive = work / "tracked.tar"
    with archive.open("wb") as stream:
        subprocess.run([*git, "archive", BASE, str(FIXTURE)], stdout=stream, check=True, timeout=15)
    with tarfile.open(archive) as tracked:
        tracked.extractall(work, filter="data")
    fixture = work / FIXTURE
    results = fixture / "evidence.json"
    expected = json.loads(results.read_bytes())
    binaries = {"dafny": args.dafny}
    for version in expected["solver_sha256"]:
        binaries[f"z3/bin/z3-{version}"] = args.dafny.parent / f"z3/bin/z3-{version}"
    installed = {}
    with ZipFile(args.archive) as package:
        for name, binary in binaries.items():
            digest = sha(binary)
            assert digest == sha256(package.read(f"dafny/{name}")).hexdigest()
            installed[name] = digest

    env = dict(os.environ, PYTHONHASHSEED="1", LC_ALL="C", PYTHONDONTWRITEBYTECODE="1")
    command = [sys.executable, str(fixture / "run.py"), "--dafny", str(args.dafny), "--archive", str(args.archive)]
    observed = subprocess.run(command, cwd=work, env=env, capture_output=True, check=True, timeout=120).stdout
    if observed != results.read_bytes():
        raise ValueError("Reproduced Dafny ledger differs from the tracked bytes")
    assert expected["proofs"]["4.12.1"] == expected["proofs"]["4.14.1"]
    assert expected["assumption_audit"]["explicit_assumption_column"] == ["False", "False"]
    for name, digest in expected["inputs_sha256"].items():
        assert sha(fixture / name) == digest

    chart = subprocess.check_output([sys.executable, fixture / "chart.py"], cwd=work, env=env)
    report_path = FIXTURE.parent / "RT-07-DAFNY-CONCURRENT-FRAME-HISTORY-2026-11-25.md"
    report = subprocess.check_output([*git, "show", f"{BASE}:{report_path}"])
    chart_rows = [line for line in chart.splitlines() if line.startswith(b"| ") and b"|---" not in line]
    assert all(line in report for line in chart_rows)
    return {
        "revision": BASE, "python": sys.version.split()[0],
        "host": {"machine": platform.machine(), "kernel": platform.release(),
                 "libc": subprocess.check_output(["getconf", "GNU_LIBC_VERSION"], text=True).strip()},
        "tools": expected["tools"], "gcc_sha256": sha(Path(shutil.which("gcc"))),
        "upstream_release_sha256": PACKAGE_HASH, "archive_matched_binaries_sha256": installed,
        "ledger_sha256": sha(results), "inputs_sha256": expected["inputs_sha256"],
        "report_tables": {"checked_rows": len(chart_rows), "sha256": sha256(chart).hexdigest()},
        "proofs": expected["proofs"], "explicit_assumption_findings": len(expected["assumption_audit"]["rows"]),
        "history_checks": check_histories(expected),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dafny", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.dafny, args.archive = args.dafny.resolve(strict=True), args.archive.resolve(strict=True)
    with TemporaryDirectory(prefix="llmlang-dafny-frame-") as directory:
        evidence = replay(args, Path(directory))
    args.out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
