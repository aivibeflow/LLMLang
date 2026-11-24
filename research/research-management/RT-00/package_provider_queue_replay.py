#!/usr/bin/env python3
"""Replay the Provider's SQLite pending-queue comparison and plot paired results."""

import argparse
from collections import defaultdict
import io
import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
from statistics import median
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory

FAMILY = Path("research/packages-and-ecosystem/PROTOTYPES")
PROVIDER = "PACKAGE-INDEX-01"
IDENTITY = "PACKAGE-IDENTITY-01"
SHAPES = ("chain", "diamond", "fanout", "many-dependencies")
CREATE_INDEX = "CREATE INDEX queue_pending_order ON queue(processed, hash);"
LOOKUP = "SELECT hash FROM queue WHERE processed = 0 ORDER BY hash LIMIT 1"


def git(*args):
    return subprocess.check_output(["git", *args])


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Expected one instance of {old}")
    return text.replace(old, new)


def prepare(root, baseline):
    archive = git("archive", baseline, str(FAMILY / PROVIDER), str(FAMILY / IDENTITY))
    with tarfile.open(fileobj=io.BytesIO(archive)) as packed:
        packed.extractall(root, filter="data")
    indexed = root / "indexed"
    (root / FAMILY).rename(indexed)
    benchmark = indexed / PROVIDER / "benchmark_package_provider.py"
    text = benchmark.read_text(encoding="utf-8")
    text = replace_once(text, "archive_bytes = os.path.getsize(archive)", """archive_bytes = os.path.getsize(archive)
        with open(archive, "rb") as built_archive:
            archive_sha256 = hashlib.file_digest(built_archive, "sha256").hexdigest()""")
    text = replace_once(text, '"archive_bytes": archive_bytes,',
                        '"archive_bytes": archive_bytes,\n        "archive_sha256": archive_sha256,')
    benchmark.write_text(text, encoding="utf-8")
    scan = root / "scan"
    shutil.copytree(indexed, scan)
    source = scan / PROVIDER / "package_provider.py"
    source.write_text(replace_once(source.read_text(encoding="utf-8"), CREATE_INDEX, ""),
                      encoding="utf-8")


def query_plan(indexed):
    with sqlite3.connect(":memory:") as connection:
        connection.execute("CREATE TABLE queue (hash TEXT PRIMARY KEY, processed INTEGER NOT NULL)")
        if indexed:
            connection.execute(CREATE_INDEX)
        return [row[3] for row in connection.execute("EXPLAIN QUERY PLAN " + LOOKUP)]


def run_case(directory, shape, size):
    output = subprocess.check_output(
        [sys.executable, "-B", "benchmark_package_provider.py", "--worker", shape, str(size)],
        cwd=directory / PROVIDER,
        env={**os.environ, "PYTHONPATH": str(directory / IDENTITY)},
    )
    return json.loads(output)


def measure(baseline, size, repetitions):
    observations = []
    with TemporaryDirectory(prefix="llmlang-provider-queue-") as tmp:
        root = Path(tmp)
        prepare(root, baseline)
        for trial in range(repetitions):
            start = trial % len(SHAPES)
            for shape in SHAPES[start:] + SHAPES[:start]:
                order = ("indexed", "scan") if (trial + SHAPES.index(shape)) % 2 == 0 else ("scan", "indexed")
                pair = {}
                for variant in order:
                    pair[variant] = run_case(root / variant, shape, size)
                if not all(case["verified"] for case in pair.values()):
                    raise ValueError(f"Invalid archive for {shape}, trial {trial + 1}")
                if pair["indexed"]["archive_sha256"] != pair["scan"]["archive_sha256"]:
                    raise ValueError(f"Archive bytes differ for {shape}, trial {trial + 1}")
                observations.append({"shape": shape, "trial": trial + 1, "order": order, **pair})
                print(f"{shape} trial {trial + 1}/{repetitions}: verified identical archive", flush=True)
    source_files = ("package_provider.py", "package_archive.py", "benchmark_package_provider.py")
    return {
        "schema": "rt00-provider-queue-replay-v1",
        "baseline": baseline,
        "source_git_blobs": {file: git("rev-parse", f"{baseline}:{FAMILY / PROVIDER / file}").decode("ascii").strip()
                             for file in source_files},
        "environment": {"python": sys.version, "sqlite": sqlite3.sqlite_version,
                        "git": git("--version").decode("ascii").strip(), "platform": platform.platform(),
                        "logical_cpus": os.cpu_count()},
        "objects_per_case": size,
        "paired_repetitions": repetitions,
        "query_plans": {"indexed": query_plan(True), "scan": query_plan(False)},
        "observations": observations,
    }


def plot(data, output):
    import matplotlib.pyplot as plt

    by_shape = defaultdict(list)
    for row in data["observations"]:
        by_shape[row["shape"]].append(row)
    fig, ax = plt.subplots(figsize=(8.4, 4.3), layout="constrained")
    groups = [
        [row["scan"]["provider_build_seconds"] / row["indexed"]["provider_build_seconds"]
         for row in by_shape[shape]]
        for shape in SHAPES
    ]
    centers = [median(group) for group in groups]
    errors = [[m - min(g) for m, g in zip(centers, groups, strict=True)],
              [max(g) - m for m, g in zip(centers, groups, strict=True)]]
    ax.axhline(1, color="0.4", linestyle="--", label="Equal build time")
    ax.errorbar(range(len(SHAPES)), centers, yerr=errors, fmt="o",
                markersize=7, capsize=4, label="Median and observed range")
    ax.set_xticks(range(len(SHAPES)), ("Chain", "Diamond", "Fan-out", "Many dependencies"))
    ax.set_ylabel("Build time without secondary index / with index")
    ax.set_title(f"SQLite queue by workload · {data['objects_per_case']:,} objects")
    ax.grid(axis="y", alpha=.25)
    ax.legend(loc="upper left", title=f"{data['paired_repetitions']} paired runs per shape")
    fig.savefig(output, dpi=160)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    run = commands.add_parser("measure")
    run.add_argument("--baseline", required=True)
    run.add_argument("--size", default=1000, type=int)
    run.add_argument("--repetitions", default=5, type=int)
    run.add_argument("--output", required=True, type=Path)
    chart = commands.add_parser("plot")
    chart.add_argument("--input", required=True, type=Path)
    chart.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.mode == "measure":
        if args.size < 1 or args.repetitions < 1:
            parser.error("size and repetitions must be positive")
        data = measure(args.baseline, args.size, args.repetitions)
        args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    else:
        plot(json.loads(args.input.read_text(encoding="utf-8")), args.output)
