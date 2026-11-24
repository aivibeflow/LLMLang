"""Measure per-dispatch CPU charges across native worker migration."""
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory

SOURCE = Path(__file__).with_name("probe.c")
MS = 1_000_000
TOLERANCE = 6 * MS


def near(measured, expected):
    return abs(measured - expected) <= TOLERANCE


def classify(span, reference):
    if near(span, reference):
        return "matching"
    return "under" if span < reference else "over"


def observe(executable):
    lines = subprocess.check_output([executable], text=True, timeout=30).splitlines()
    ledger = {}
    samples = {}
    for line in lines:
        name, *values = line.split(",")
        resumed, cancelled, first, other, second, origin, cross, worker0, worker1, process = map(int, values)
        expected_other = 0 if name == "migrate-alone" else 40 * MS
        assert near(first, 30 * MS) and near(second, (12 if cancelled else 25) * MS)
        assert near(other, expected_other)
        task = first + second
        scheduled = task + other
        assert near(worker0 + worker1, scheduled) and near(process, scheduled)
        assert near(worker0, scheduled if resumed == 0 else first + other)
        assert near(worker1, 0 if resumed == 0 else second)
        if resumed:
            assert cross < 0, (name, cross)
        else:
            assert near(cross, scheduled)
        origin_class = classify(origin, task)
        assert origin_class == ("under" if name == "migrate-alone" else "over")
        ledger[name] = {"moves_between_workers": bool(resumed), "cancelled": bool(cancelled),
                        "origin_clock_charge": origin_class,
                        "cross_clock_is_negative": cross < 0,
                        "worker_total_matches_dispatches": True, "process_matches_dispatches": True}
        samples[name] = {"first_task_ns": first, "peer_ns": other, "second_task_ns": second,
                         "origin_span_ns": origin, "cross_worker_subtraction_ns": cross,
                         "worker_0_ns": worker0, "worker_1_ns": worker1, "process_ns": process}
    assert len(ledger) == 4
    return ledger, samples


def run(options):
    ledger = {}
    samples = {}
    with TemporaryDirectory(prefix="llmlang-task-cpu-") as directory:
        executable = Path(directory) / "probe"
        for optimization in ("0", "3"):
            subprocess.run([options.cc, "-std=c17", "-Wall", "-Wextra", "-Werror", "-pthread",
                            f"-O{optimization}", SOURCE, "-o", executable], check=True, timeout=30)
            ledger[f"O{optimization}"], samples[f"O{optimization}"] = observe(executable)
    assert ledger["O0"] == ledger["O3"]
    output = {"format": "rt26-migrating-task-cpu/1", "python": sys.version.split()[0],
              "cc": subprocess.check_output([options.cc, "--version"], text=True, timeout=15).splitlines()[0],
              "machine": platform.machine(), "kernel": platform.release(), "tolerance_ns": TOLERANCE,
              "outcomes": ledger}
    options.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if options.sample:
        options.sample.write_text(json.dumps(samples, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--sample", type=Path)
    run(parser.parse_args())
