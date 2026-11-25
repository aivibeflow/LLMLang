"""Check exact CPU-timer scope and archive host-specific raw latency observations."""

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
import os
from pathlib import Path
from statistics import median
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
FIELDS = ("round", "scope", "budget_ns", "pending_after_peer", "worker_before_ns",
          "clock_at_observation_ns", "worker_at_observation_ns", "wall_at_observation_ns", "peer_cpu_ns")


def process(*args):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=30).stdout.strip()


def encode(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def collect(args, work):
    source = HERE / "timers.c"
    executable = work / "timers"
    process(args.cc, "-std=c17", "-O2", "-Wall", "-Wextra", "-Werror", "-pthread", source, "-o", executable)
    records = []
    counts = Counter()
    overshoot = defaultdict(list)
    for row in process(executable).splitlines():
        parsed = {
            name: item if name == "scope" else int(item)
            for name, item in zip(FIELDS, row.split(), strict=True)
        }
        scope = parsed["scope"]
        budget = parsed["budget_ns"]
        assert scope in {"process", "worker"} and budget in {5000000, 10000000, 20000000}
        assert parsed["pending_after_peer"] == (scope == "process")
        assert parsed["peer_cpu_ns"] >= 2 * budget
        assert parsed["worker_before_ns"] < budget
        assert parsed["clock_at_observation_ns"] >= budget
        if scope == "worker":
            assert parsed["worker_at_observation_ns"] >= budget
        else:
            assert parsed["worker_at_observation_ns"] < budget
        label = f"{scope}/{budget}"
        counts[label] += 1
        overshoot[label].append(parsed["clock_at_observation_ns"] - budget)
        records.append(parsed)
    assert len(records) == 120 and set(counts.values()) == {20}
    assert len({(row["scope"], row["budget_ns"], row["round"]) for row in records}) == 120
    stable = {
        "source_sha256": sha256(source.read_bytes()).hexdigest(),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "profiles": dict(sorted(counts.items())), "native_trials": len(records),
        "process_elapsed_while_worker_below_budget": 60,
        "worker_elapsed_only_after_local_cpu": 60,
    }
    measurement = {
        "clock": "Linux timer_create with per-process or per-thread CPU clock",
        "kernel": os.uname().release, "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "compiler": process(args.cc, "--version").splitlines()[0], "cpu_over_budget_at_observation_ns": {
            name: {"minimum": min(values), "median": median(values), "maximum": max(values)}
            for name, values in overshoot.items()
        },
        "samples": records,
    }
    return stable, measurement


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--measurements", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt26-cpu-timers-") as directory:
        stable, measurement = collect(args, Path(directory))
    args.output.write_text(encode(stable), encoding="utf-8")
    if args.measurements:
        args.measurements.write_text(encode(measurement), encoding="utf-8")
