"""Run scoped concurrent virtual-address exhaustion across five pinned allocators."""

import argparse
import errno
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
ARCHIVE = HERE.parent / "ALLOCATOR-CONCURRENT-01/evidence.json"
SEED = 2527
PROVIDERS = ("glibc", "jemalloc", "mimalloc", "gperftools", "google")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def run(args, **options):
    return subprocess.check_output(args, text=True, timeout=20, **options)


def check(options):
    archived = json.loads(ARCHIVE.read_text())
    paths = {name: getattr(options, name).resolve() for name in PROVIDERS}
    for name, path in paths.items():
        assert digest(path) == archived["libraries"][name]["sha256"], (name, path)
    selected = sorted(os.sched_getaffinity(0))[:4]
    os.sched_setaffinity(0, selected)
    randomizer = random.Random(SEED)
    rows = []
    with TemporaryDirectory() as directory:
        binary = Path(directory) / "pressure"
        run(["cc", "-std=c17", "-O2", "-Wall", "-Wextra", "-Werror", "-pthread", "-Wl,--build-id=none",
             HERE / "pressure.c", "-o", binary, "-ldl"])
        for sample in range(7):
            cases = list(product(PROVIDERS, (2, 4), (96, 192), (False, True)))
            randomizer.shuffle(cases)
            for provider, workers, cap, early in cases:
                env = {**os.environ, "LD_PRELOAD": str(paths[provider]), "LC_ALL": "C"}
                try:
                    origin, budget, *trace = run([binary, str(workers), str(cap), str(int(early))], env=env).splitlines()
                except subprocess.CalledProcessError as failure:
                    raise ValueError((provider, workers, cap, early, failure.output)) from failure
                assert Path(origin).resolve() == paths[provider]
                label, used = budget.split()
                assert label == "activation-kib" and int(used) > 0
                row = {"sample": sample, "provider": provider, "workers": workers, "cap_mib": cap,
                       "virtual_kib_at_activation": int(used),
                       "cap_before_workers": early}
                if trace[0].startswith("startup-refused"):
                    assert len(trace) == 1 and early
                    _, code, created = trace[0].split()
                    assert int(code) == errno.EAGAIN and int(created) < workers
                    rows.append({**row, "startup_error": int(code), "workers_created": int(created)})
                    continue
                assert len(trace) == workers
                batches = [{"held": int(count), "retried": bool(int(retry)), "reserve_ns": int(elapsed),
                            "stop": "quota" if int(count) == 16 else "fallible-refusal"}
                           for count, retry, elapsed in (line.split() for line in trace)]
                assert all(0 <= worker["held"] <= 16 for worker in batches)
                assert all(item["reserve_ns"] > 0 for item in batches)
                rows.append({**row, "per_thread": batches})
        executable = digest(binary)
    return {"samples": rows, "build_sha256": executable, "sources_sha256": {
                name: digest(HERE / name) for name in ("check.py", "pressure.c")},
            "prior_library_ledger_sha256": digest(ARCHIVE),
            "providers": {name: digest(path) for name, path in paths.items()},
            "compiler": run(["cc", "--version"]).splitlines()[0], "host": platform.platform(),
            "cpu_model": next(line.partition(":")[2].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                              if line.startswith("model name")),
            "cpu_affinity": selected, "seed": SEED}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in PROVIDERS:
        parser.add_argument(f"--{name}", required=True, type=Path)
    print(json.dumps(check(parser.parse_args()), indent=2, sort_keys=True))
