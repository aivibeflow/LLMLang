"""Measure scoped user-space task/ancestor read admission with native read timings."""

from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import platform
import random
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
SEED = 2627
COUNT = 512
BYTES = 16


def run(args):
    return subprocess.check_output(args, text=True, timeout=20)


def check():
    selected = sorted(os.sched_getaffinity(0))[:4]
    os.sched_setaffinity(0, selected)
    randomizer = random.Random(SEED)
    rows = []
    with TemporaryDirectory() as directory:
        folder = Path(directory)
        fixture, executable = folder / "fixture", folder / "probe"
        fixture.write_bytes(bytes(range(128)))
        run(["cc", "-std=c17", "-O2", "-Wall", "-Wextra", "-Werror", "-pthread", "-Wl,--build-id=none",
             HERE / "bench.c", "-o", executable])
        for sample in range(18):
            cases = list(product((1, 4), ("raw", "hierarchy")))
            randomizer.shuffle(cases)
            for workers, policy in cases:
                first, *more = run([executable, fixture, str(workers), policy]).splitlines()
                elapsed, parent_left = map(int, first.split())
                events = [tuple(map(int, line.split())) for line in more]
                admitted = [ns for passed, ns in events if passed]
                refused = [ns for passed, ns in events if not passed]
                assert len(admitted) == len(refused) == workers * COUNT // 2
                total = len(admitted) * BYTES
                assert parent_left == (0 if policy == "hierarchy" else total)
                rows.append({"sample": sample, "workers": workers, "policy": policy,
                             "elapsed_ns": elapsed, "committed_bytes": total,
                             "admit_ns": admitted, "refuse_ns": refused})
        artifact = sha256(executable.read_bytes()).hexdigest()
    return {"platform": platform.platform(), "cpu_affinity": selected,
            "compiler": run(["cc", "--version"]).splitlines()[0],
            "source_sha256": sha256((HERE / "bench.c").read_bytes()).hexdigest(),
            "binary_sha256": artifact, "seed": SEED, "samples": rows}


if __name__ == "__main__":
    # Preserve per-request samples without adding a multiline block per datum.
    print(json.dumps(check(), separators=(",", ":"), sort_keys=True))
