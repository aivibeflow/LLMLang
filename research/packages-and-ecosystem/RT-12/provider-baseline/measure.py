"""Collect independent Provider benchmark processes in a fixed shuffled order."""
import argparse
import csv
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time

PACKAGE = Path(__file__).resolve().parents[2] / "PROTOTYPES"
BENCHMARK = PACKAGE / "PACKAGE-INDEX-01" / "benchmark_package_provider.py"
SHAPES = ("chain", "diamond", "fanout", "many-dependencies")
SIZES = (128, 1200, 4096)


def collect(output, repeats):
    environment = dict(os.environ, PYTHONHASHSEED="0",
                       PYTHONPATH=str(PACKAGE / "PACKAGE-IDENTITY-01"))
    rng = random.Random(333)
    expected = {}
    with output.open("x", newline="") as stream:
        writer = None
        for trial in range(1, repeats + 1):
            cases = [(shape, size) for shape in SHAPES for size in SIZES]
            rng.shuffle(cases)
            for order, (shape, size) in enumerate(cases, start=1):
                started = time.perf_counter()
                result = subprocess.run(
                    [sys.executable, str(BENCHMARK), "--worker", shape, str(size)],
                    env=environment, capture_output=True, text=True, check=True,
                )
                wall_seconds = round(time.perf_counter() - started, 6)
                sample = json.loads(result.stdout)
                assert (sample["shape"], sample["objects"], sample["verified"]) == (
                    shape, size, True,
                )
                counts = tuple(sample[key] for key in (
                    "dependency_edges", "manifest_bytes", "archive_bytes",
                ))
                assert counts == expected.setdefault((shape, size), counts)
                row = {"trial": trial, "order": order, **sample,
                       "subprocess_wall_seconds": wall_seconds}
                if writer is None:
                    writer = csv.DictWriter(stream, fieldnames=row, lineterminator="\n")
                    writer.writeheader()
                writer.writerow(row)
                stream.flush()
                print(trial, shape, size, sample["provider_build_seconds"], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    collect(args.output, args.repeats)


if __name__ == "__main__":
    main()
