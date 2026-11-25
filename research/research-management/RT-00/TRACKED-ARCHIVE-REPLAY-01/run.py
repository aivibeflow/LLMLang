"""Replay a pinned set of research receipts from a tracked Git archive."""

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory


BASE = "efbcf8ef1ba71e8c4d8d219654ea8ab38ab9040d"
TREE = "2af775e171361b78fa3ba1c2a6c471d07846ff34"
COMPILER = "research/compiler-and-translation"
RUNTIME = "research/runtime-and-systems/RT-10"
PACKAGE = "research/packages-and-ecosystem/RT-12"
TYPES = "research/semantic-representation/RT-05"
SECURITY = "research/security/RT-16"
CONTEXT = "research/toolchain-and-collaboration/RT-14"
SYNTAX = "research/language-design/RT-31"


@dataclass(frozen=True)
class Route:
    directory: str
    runner: str = "run.py"
    arguments: tuple[str, ...] = ()


ROUTES = (
    Route(f"{RUNTIME}/POSIX-FILE-IDENTITY-01"),
    Route(f"{RUNTIME}/POSIX-SPAWN-DESCRIPTORS-01"),
    Route(f"{RUNTIME}/POSIX-CROSS-LIBC-01", arguments=("--musl-root", "{musl_root}")),
    Route(f"{COMPILER}/RT-13/WIDE-DIVISION-CAPABILITY-01"),
    Route(f"{COMPILER}/RT-13/GENERATED-PYTHON-INTEGERS-01"),
    Route(f"{COMPILER}/RT-13/IMPLEMENTATION-FALLBACK-01"),
    Route(f"{COMPILER}/RT-13/DISPATCH-TIMING-01",
          arguments=("--go-cache", "{go_cache}", "--samples", "{scratch}/dispatch.csv", "--trials", "1")),
    Route(f"{CONTEXT}/KNOWLEDGE-CONTEXT-01"),
    Route(f"{CONTEXT}/TASK-CONTEXT-COMPLETION-01"),
    Route(f"{SYNTAX}/MCP-ATTRIBUTION-01"),
    Route(f"{COMPILER}/RT-30/GO-ROUNDTRIP-01", "roundtrip.py", ("--cache", "{go_cache}")),
    Route(f"{COMPILER}/RT-30/C-FAMILY-ROUNDTRIP-01", "roundtrip.py"),
    Route(f"{COMPILER}/RT-30/RUST-WRAPPING-ROUNDTRIP-01", "roundtrip.py"),
    Route(f"{COMPILER}/RT-30/WRAPPING-TRANSLATION-MATRIX-01", "matrix.py", ("--cache", "{go_cache}")),
    Route(f"{COMPILER}/RT-30/PROVENANCE-ROUTES-01"),
    Route(f"{COMPILER}/RT-30/SHARED-C-RUNTIME-01", arguments=("--go-cache", "{go_cache}")),
    Route(f"{PACKAGE}/INDEX-COMPRESSION-01",
          arguments=("--trials", "0", "--measurements", "{scratch}/compression-memory.csv")),
    Route(f"{PACKAGE}/INDEX-INTEGRITY-01", "sparse.py"),
    Route(f"{PACKAGE}/HIERARCHICAL-DIRECTORY-01"),
    Route(f"{PACKAGE}/INDEPENDENT-PACKAGE-IDENTITY-01"),
    Route(f"{PACKAGE}/CONDITIONAL-CLOSURE-01"),
    Route(f"{SECURITY}/BUILD-ATTESTATION-01"),
    Route(f"{SECURITY}/PROOF-REVOCATION-01"),
    Route(f"{TYPES}/NATIVE-TYPE-IDENTITY-01"),
    Route(f"{TYPES}/NATIVE-TYPESTATE-01"),
    Route(f"{TYPES}/SUM-EXTENSION-01"),
)
PLOTS = (
    (f"{PACKAGE}/INDEX-COMPRESSION-01", "evidence.json", "index-compression.svg"),
    (f"{PACKAGE}/HIERARCHICAL-DIRECTORY-01", "evidence.json", "hierarchy-lookup.svg"),
    (f"{COMPILER}/RT-13/DISPATCH-TIMING-01", "samples.csv", "dispatch-latency.svg"),
)


def command(args, directory, env):
    finished = subprocess.run(args, cwd=directory, env=env, capture_output=True, timeout=180)
    if finished.returncode:
        raise RuntimeError((args[0], finished.returncode, finished.stderr.decode(errors="replace")[-4000:]))
    return finished.stdout


def hash_bytes(contents):
    return sha256(contents).hexdigest()


def hash_path(path):
    return hash_bytes(path.read_bytes())


def archive_repository(repo, scratch, env):
    if command(["git", "rev-parse", f"{BASE}^{{tree}}"], repo, env).decode().strip() != TREE:
        raise ValueError("The recorded baseline tree is unavailable")
    output = scratch / "research.tar"
    with output.open("wb") as tar:
        subprocess.run(["git", "archive", "--format=tar", BASE, "research"], cwd=repo,
                       env=env, stdout=tar, check=True, timeout=120)
    checkout = scratch / "archive"
    checkout.mkdir()
    with tarfile.open(output) as tar:
        tar.extractall(checkout, filter="data")
    return checkout



def archived_timing(checkout):
    dispatch = checkout / COMPILER / "RT-13" / "DISPATCH-TIMING-01"
    dispatch_expected = json.loads((dispatch / "evidence.json").read_text())
    dispatch_samples = dispatch / "samples.csv"
    with dispatch_samples.open(newline="") as sample:
        rows = list(csv.DictReader(sample))
    dispatch_trials = Counter()
    for row in rows:
        workload = dispatch_expected["checked_workloads"][row["workload"]]
        if (int(row["elapsed_ns"]) <= 0 or int(row["calls"]) != dispatch_expected["calls_per_trial"]
                or int(row["checksum"]) != workload["timed_checksum"]):
            raise ValueError(("invalid archived dispatch sample", row))
        dispatch_trials[int(row["trial"]), row["workload"], row["adapter"]] += 1
    dispatch_matrix = set(product(range(1, 8), dispatch_expected["checked_workloads"],
                                  ("native-runtime", "c", "cpp", "go", "rust")))
    if set(dispatch_trials) != dispatch_matrix or set(dispatch_trials.values()) != {1}:
        raise ValueError("Unexpected archived dispatch matrix")

    compression = checkout / PACKAGE / "INDEX-COMPRESSION-01"
    compression_expected = json.loads((compression / "evidence.json").read_text())
    compression_samples = compression / "trials.csv"
    with compression_samples.open(newline="") as sample:
        rows = list(csv.DictReader(sample))
    distinct = Counter()
    timing = memory = 0
    for row in rows:
        expected = compression_expected["layouts"][row["layout"]]["operations"][row["operation"]]
        if int(row["read_bytes"]) != expected["read_bytes"]:
            raise ValueError(("wrong archived read volume", row))
        if row["trial"] == "trace":
            if row["elapsed_ns"] or int(row["python_peak_bytes"]) <= 0:
                raise ValueError(("invalid allocation trace", row))
            memory += 1
        else:
            if row["python_peak_bytes"] or int(row["elapsed_ns"]) <= 0:
                raise ValueError(("invalid timing sample", row))
            timing += 1
        distinct[row["trial"], row["layout"], row["operation"]] += 1
    compression_matrix = {
        (trial, layout, operation)
        for trial in ("trace", *map(str, range(1, 8)))
        for layout, evidence in compression_expected["layouts"].items()
        for operation in evidence["operations"]
    }
    if set(distinct) != compression_matrix or set(distinct.values()) != {1}:
        raise ValueError("Unexpected archived compression matrix")
    return {
        "dispatch_intervals": len(dispatch_trials),
        "compression_intervals": timing,
        "compression_memory_traces": memory,
    }

def replay(args, scratch):
    env = {**os.environ, "LC_ALL": "C", "MPLCONFIGDIR": str(scratch / "matplotlib"),
           "GOCACHE": str(args.go_cache.resolve())}
    base = archive_repository(args.repo.resolve(), scratch, env)
    inputs = {"scratch": str(scratch), "go_cache": str(args.go_cache.resolve()),
              "musl_root": str(args.musl_root.resolve())}

    replays = []
    for route in ROUTES:
        print(f"Replaying {Path(route.directory).name}", file=sys.stderr)
        runner = Path(route.directory) / route.runner
        expected_path = Path(route.directory) / "evidence.json"
        options = tuple(arg.format_map(inputs) for arg in route.arguments)
        observed = command([sys.executable, "-B", str(runner), *options], base, env)
        expected = (base / expected_path).read_bytes()
        if observed != expected:
            differences = []
            try:
                left, right = json.loads(expected), json.loads(observed)
                differences = [key for key in sorted(set(left) | set(right)) if left.get(key) != right.get(key)]
            except (ValueError, AttributeError, TypeError):
                pass
            raise AssertionError((str(expected_path), hash_bytes(expected), hash_bytes(observed), differences))
        replays.append({"runner": str(runner), "runner_sha256": hash_path(base / runner),
                        "evidence": str(expected_path), "bytes": len(expected),
                        "expected_sha256": hash_bytes(expected), "observed_sha256": hash_bytes(observed)})

    figures = []
    for directory, asset, figure in PLOTS:
        root = Path(directory)
        destination = scratch / figure
        command([sys.executable, "-B", str(root / "plot.py"), str(root / asset), str(destination)],
                base, env)
        original = base / root / figure
        if destination.read_bytes() != original.read_bytes():
            raise AssertionError((figure, "archived figure changed"))
        figures.append({"figure": str(root / figure), "data": str(root / asset),
                        "bytes": original.stat().st_size, "sha256": hash_path(original)})
    return {
        "baseline_commit": BASE,
        "baseline_tree": TREE,
        "exact_receipts": len(replays),
        "exact_figures": len(figures),
        "replays": replays,
        "figures": figures,
        "archive_measurements_checked": archived_timing(base),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=Path.cwd(), type=Path)
    parser.add_argument("--go-cache", required=True, type=Path)
    parser.add_argument("--musl-root", required=True, type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-tracked-archive-") as temp:
        print(json.dumps(replay(args, Path(temp)), indent=2))


if __name__ == "__main__":
    main()
