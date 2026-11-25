"""Check the modern TCMalloc runtime binding and compare one Rust workload."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
from random import Random
from statistics import median, quantiles
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
PROTOTYPES = HERE.parents[1] / "PROTOTYPES"
COMPAT = PROTOTYPES / "ALLOCATOR-COMPAT-01" / "probe.rs"
GRAPH = PROTOTYPES / "ALLOCATOR-BENCH-01" / "graph.rs"
WANTED = "4c66d60dbdbdf118"
FIELDS = ("build_ns", "impact_ns", "baseline_kib", "live_kib", "peak_kib", "after_drop_kib")


def run(*command, env=None):
    result = subprocess.run(command, text=True, capture_output=True, check=True, timeout=30, env=env)
    if result.stderr:
        raise ValueError(result.stderr)
    return result.stdout.strip()


def stats(values):
    cuts = quantiles(values, n=10, method="inclusive")
    return {"median": median(values), "p10": cuts[0], "p90": cuts[-1], "n": len(values)}


def cpu_counters():
    return {key: int(value) for key, value in
            map(str.split, Path("/sys/fs/cgroup/cpu.stat").read_text().splitlines())}


def measure(args, scratch):
    clean = {key: value for key, value in os.environ.items()
             if key != "LD_PRELOAD" and not key.startswith(("TCMALLOC_", "MALLOC_", "MIMALLOC_", "GLIBC_TUNABLES"))}
    clean["LC_ALL"] = "C"
    modern = {**clean, "LD_PRELOAD": str(args.library)}
    versions = {
        "rustc": run(args.rustc, "--version", env=clean),
        "glibc": run("getconf", "GNU_LIBC_VERSION", env=clean),
        "python": platform.python_version(),
        "nm": run("nm", "--version", env=clean).splitlines()[0],
    }
    names = {line.split()[-1] for line in run("nm", "-D", "--defined-only", args.library, env=clean).splitlines()}
    requested = {"malloc", "calloc", "realloc", "free", "posix_memalign", "llmlang_tcmalloc_per_cpu_caches"}
    if not requested <= names:
        raise ValueError(("missing dynamic allocator symbols", sorted(requested - names)))
    baseline = ("libc.so.6", clean)
    tcmalloc = (args.library.name, modern)
    executables = {}
    for label, path in (("compatibility", COMPAT), ("graph", GRAPH)):
        executable = scratch / label
        run(args.rustc, "--edition", "2021", "-C", "opt-level=3", path, "-o", executable, env=clean)
        executables[label] = executable

    compatibility = {}
    providers = {"glibc": baseline, "modern-google-tcmalloc": tcmalloc}
    for label, (expected, env) in providers.items():
        result = run(executables["compatibility"], expected, env=env)
        if not result.endswith(": 3200 Rust allocation sequences and C resize-failure check passed"):
            raise ValueError((label, result))
        resolved = Path(result.split(":", 1)[0]).resolve()
        if label == "modern-google-tcmalloc" and resolved != args.library:
            raise ValueError("wrong TCMalloc library loaded")
        compatibility[label] = {"library_basename": resolved.name, "sha256": sha256(resolved.read_bytes()).hexdigest(),
                                "rust_sequences": 3200, "impossible_c_resize": "original storage preserved"}
    per_cpu = int(run(
        sys.executable, "-c",
        "import ctypes; print(ctypes.CDLL(None).llmlang_tcmalloc_per_cpu_caches())", env=modern))
    if per_cpu not in (0, 1):
        raise ValueError("unexpected per-CPU mode response")
    cpu = args.cpu
    if cpu not in os.sched_getaffinity(0) or args.trials < 2:
        raise ValueError("invalid CPU or trial count")
    os.sched_setaffinity(0, {cpu})
    random = Random(args.seed)
    rows = []
    before = cpu_counters()
    for block in range(args.trials):
        ordered = list(providers)
        random.shuffle(ordered)
        for position, label in enumerate(ordered):
            expected, env = providers[label]
            report = json.loads(run(executables["graph"], expected, env=env))
            if report["checksum"] != WANTED or any(report[key] <= 0 for key in FIELDS):
                raise ValueError((label, report))
            rows.append({"provider": label, "block": block, "position": position, **report})
    after = cpu_counters()
    return {
        "cpu": cpu, "cpu_model": next(line.split(":", 1)[1].strip()
            for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("model name")),
        "kernel": platform.release(), "tools": versions, "trials": args.trials, "seed": args.seed,
        "compatibility": compatibility, "modern_non_graph_process_per_cpu_caches": bool(per_cpu),
        "cpu_counter_delta": {key: after[key] - before[key] for key in before},
        "source_sha256": {"probe": sha256(COMPAT.read_bytes()).hexdigest(), "graph": sha256(GRAPH.read_bytes()).hexdigest(),
                          **{name: sha256((HERE / name).read_bytes()).hexdigest()
                             for name in ("run.py", "BUILD.bazel", "bridge.cc")}},
        "samples": rows,
        "summary": {label: {field: stats([row[field] for row in rows if row["provider"] == label]) for field in FIELDS}
                    for label in providers},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("rustc", "library", "output"):
        parser.add_argument(f"--{argument}", required=True, type=Path)
    parser.add_argument("--cpu", required=True, type=int)
    parser.add_argument("--trials", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    args = parser.parse_args()
    args.library = args.library.resolve()
    with TemporaryDirectory(prefix="rt25-modern-allocator-") as scratch:
        receipt = measure(args, Path(scratch))
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
