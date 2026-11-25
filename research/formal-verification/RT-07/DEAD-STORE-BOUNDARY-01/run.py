#!/usr/bin/env python3
"""Validate the exact observation boundary of an overwritten store removal."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import shutil
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
SAMPLES = (0, 1, 255)


def expected(visible, route, removed, initial, other, first, last):
    subject = initial if removed else first
    load = (-1, subject, other)[route]
    trace = () if not visible else (last,) if removed else (first, last)
    return (last, other, load, *trace)


def command(args, root, *, source=None):
    return subprocess.run(args, cwd=root, input=source, check=True, capture_output=True,
                          text=True, timeout=30).stdout


def compare():
    profiles = list(product((0, 1), (0, 1, 2), *([SAMPLES] * 4)))
    observations = []
    counts = {name: Counter() for name in ("final_cells", "hidden_write", "exact_rule")}
    witnesses = {}
    for visible, route, initial, other, first, last in profiles:
        axes = (visible, route, initial, other, first, last)
        source = expected(visible, route, 0, initial, other, first, last)
        target = expected(visible, route, 1, initial, other, first, last)
        equal = source == target
        guards = {
            "final_cells": source[:2] == target[:2],
            "hidden_write": not visible,
            "exact_rule": not visible and (route != 1 or initial == first),
        }
        if guards["exact_rule"] != equal:
            raise AssertionError(f"Incorrect elimination criterion for {axes}")
        for name, admit in guards.items():
            counts[name]["admitted"] += admit
            counts[name]["false_admission"] += admit and not equal
            counts[name]["false_refusal"] += equal and not admit
        if not equal:
            reason = "trace" if visible else "intervening_alias_read"
            witnesses.setdefault(reason, {"profile": axes, "source": source, "after_elimination": target})
        observations.extend([((visible, route, removed, initial, other, first, last), value)
                             for removed, value in ((0, source), (1, target))])

    stdin = "".join(" ".join(map(str, data)) + "\n" for data, _ in observations)
    exact_output = "".join(" ".join(map(str, value)) + "\n" for _, value in observations)
    flags = ("-std=c17", "-Wall", "-Wextra", "-Werror")
    native = {}
    with TemporaryDirectory(prefix="llmlang-dead-store-") as directory:
        root = Path(directory)
        shutil.copyfile(HERE / "probe.c", root / "probe.c")
        compiler = command(["gcc", "--version"], root).splitlines()[0]
        for optimization in ("-O0", "-O2"):
            command(["gcc", optimization, *flags, "probe.c", "-o", "probe"], root)
            output = command(["./probe"], root, source=stdin)
            if output != exact_output:
                raise AssertionError(f"Native artifact disagrees with the bounded oracle at {optimization}")
            native[optimization] = sha256(output.encode("ascii")).hexdigest()
    return {
        "schema": "llmlang-dead-store-boundary/1", "python": platform.python_version(), "gcc": compiler,
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "Store.lean", "probe.c", "axioms.txt")},
        "profiles": len(profiles), "native_observations_per_optimization": len(observations),
        "sample_values": SAMPLES, "native_rows_sha256": native, "guards": counts, "witnesses": witnesses,
        "reference_sha256": sha256(exact_output.encode("ascii")).hexdigest(),
    }


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2))
