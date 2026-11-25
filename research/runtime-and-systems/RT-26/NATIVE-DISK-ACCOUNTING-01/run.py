#!/usr/bin/env python3
"""Compare exact logical file transfers with scoped native Linux process counters."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import permutations, product
import json
import os
from pathlib import Path
import signal
import subprocess
from tempfile import TemporaryDirectory
import time

HERE = Path(__file__).resolve().parent
FIELDS = ("rchar", "wchar", "syscr", "syscw", "read_bytes", "write_bytes", "cancelled_write_bytes")
PHASES = (
    ("buffered-write", (0, 4096, 0, 1)),
    ("cached-read", (4096, 0, 1, 0)),
    ("sparse-hole", (8192, 0, 1, 0)),
    ("flush", (0, 0, 0, 0)),
    ("repeat-overwrite", (0, 1024, 0, 2)),
    ("truncate", (0, 0, 0, 0)),
)


def observe_stopped(pid):
    deadline = time.monotonic() + 10
    while True:
        received, status = os.waitpid(pid, os.WNOHANG | os.WUNTRACED)
        if received:
            assert os.WIFSTOPPED(status) and os.WSTOPSIG(status) == signal.SIGSTOP
            break
        assert time.monotonic() < deadline
        time.sleep(0.002)
    raw = Path(f"/proc/{pid}/io").read_text()
    values = {key: int(value) for line in raw.splitlines() for key, value in [line.split(": ")]}
    return tuple(values[key] for key in FIELDS)


def measure(binary, directory):
    with subprocess.Popen([str(binary)], cwd=directory, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE) as child:
        try:
            previous = observe_stopped(child.pid)
            rows = []
            for name, logical in PHASES:
                os.kill(child.pid, signal.SIGCONT)
                current = observe_stopped(child.pid)
                differences = tuple(end - start for end, start in zip(current, previous, strict=True))
                assert differences[:4] == logical, (name, differences, logical)
                assert min(differences) >= 0
                rows.append({"phase": name, "delta": dict(zip(FIELDS, differences, strict=True))})
                previous = current
            os.kill(child.pid, signal.SIGCONT)
            output, error = child.communicate(timeout=10)
            assert child.returncode == 0 and not output and not error
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate()
    return rows


def budgets():
    # Use a model independent of kernel placement and buffering. A preflight
    # reservation charges the request maximum, then settles the actual count.
    caps = (0, 512, 4096, 8192, 12288, 16384, 17344, 17408)
    tasks = (("copy", 9000, 8192), ("hole-read", 8192, 8192), ("rewrite", 2048, 1024))
    physical = {"copy": 4096, "hole-read": 0, "rewrite": 4096}
    counts = Counter()
    for cap, order in product(caps, permutations(tasks)):
        device_remaining = cap
        logical_accepted_under_device_scope = 0
        for name, _, actual in order:
            if physical[name] <= device_remaining:
                device_remaining -= physical[name]
                logical_accepted_under_device_scope += actual
        counts["device_charge_exceeds_logical_cap"] += logical_accepted_under_device_scope > cap
        available = cap
        done = {}
        for name, maximum, actual in order:
            if maximum > available:
                counts["refused"] += 1
                continue
            available -= maximum
            assert available >= 0
            available += maximum - actual
            done[name] = actual
            counts["admitted"] += 1
            assert available == cap - sum(done.values())
        counts["histories"] += 1
    assert counts["admitted"] and counts["refused"] and counts["device_charge_exceeds_logical_cap"]
    return dict(counts)


def experiment(root):
    gcc = os.environ.get("CC", "gcc")
    runs = []
    for level in ("-O0", "-O2"):
        binary = root / f"probe-{level[1:]}"
        subprocess.run(
            [gcc, "-std=c11", "-Wall", "-Wextra", "-Werror", level,
             str(HERE / "probe.c"), "-o", str(binary)],
            cwd=root, capture_output=True, check=True,
        )
        for trial in range(1, 4):
            directory = root / f"{level[1:]}-{trial}"
            directory.mkdir()
            rows = measure(binary, directory)
            runs.append({"optimization": level, "trial": trial, "phases": rows})
    return {
        "format": "native-disk-accounting-01",
        "gcc": subprocess.check_output([gcc, "--version"], text=True).splitlines()[0],
        "kernel": os.uname().release, "logical_fields": FIELDS[:4],
        "logical_phases": PHASES, "budget_model": budgets(),
        "native_phases": sum(len(trial["phases"]) for trial in runs),
        "probe": sha256((HERE / "probe.c").read_bytes()).hexdigest(),
    }, runs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact", type=Path, required=True)
    parser.add_argument("--native", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-native-disk-") as work:
        exact, native = experiment(Path(work))
    args.exact.write_text(json.dumps(exact, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    args.native.write_text(json.dumps(native, sort_keys=True, indent=2) + "\n", encoding="utf-8")
