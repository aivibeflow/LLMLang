"""Run a graph workload in alternating isolated allocator processes."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
from statistics import median
import subprocess
from tempfile import TemporaryDirectory


SOURCE = Path(__file__).with_name("graph.rs")


def run(rustc, jemalloc, samples):
    cpu = min(os.sched_getaffinity(0))
    providers = {"glibc": None, "jemalloc": jemalloc}
    with TemporaryDirectory(prefix="llmlang-alloc-bench-") as directory:
        executable = str(Path(directory) / "graph")
        subprocess.run([rustc, "--edition=2024", "-C", "opt-level=3", "-D", "warnings",
                        str(SOURCE), "-o", executable], check=True, timeout=60)
        runs = []
        for index in range(samples):
            names = list(providers)
            if index % 2:
                names.reverse()
            for name in names:
                env = os.environ.copy()
                for setting in ("LD_PRELOAD", "MALLOC_CONF", "GLIBC_TUNABLES", "MALLOC_ARENA_MAX"):
                    env.pop(setting, None)
                if providers[name]:
                    env["LD_PRELOAD"] = providers[name]
                library = "libc.so.6" if name == "glibc" else "libjemalloc.so.2"
                output = subprocess.check_output(
                    ["taskset", "-c", str(cpu), executable, library],
                    text=True, env=env, timeout=30,
                )
                runs.append({"provider": name, **json.loads(output)})

    checksums = {sample["checksum"] for sample in runs}
    if len(checksums) != 1:
        raise ValueError(f"providers disagree on the workload checksum: {checksums}")
    versions = subprocess.check_output(["dpkg-query", "-W", "libc6", "libjemalloc2"], text=True)
    cpu_info = Path("/proc/cpuinfo").read_text().splitlines()
    cpu_name = next(line.split(":", 1)[1].strip() for line in cpu_info if line.startswith("model name"))
    return {
        "host": platform.platform(),
        "cpu": cpu_name,
        "affinity": cpu,
        "cpu_quota_period": Path("/sys/fs/cgroup/cpu.max").read_text().strip(),
        "rustc": subprocess.check_output([rustc, "--version"], text=True).strip(),
        "providers": versions.strip().splitlines(),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "samples": runs,
    }


def summary(results):
    for provider in ("glibc", "jemalloc"):
        runs = [sample for sample in results["samples"] if sample["provider"] == provider]
        print(provider)
        for field in ("build_ns", "impact_ns", "baseline_kib", "live_kib", "peak_kib", "after_drop_kib"):
            data = [sample[field] for sample in runs]
            print(f"  {field}: min={min(data)} median={median(data)} max={max(data)}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rustc", default="rustc")
    p.add_argument("--jemalloc", required=True)
    p.add_argument("--samples", type=int, default=8)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    if args.samples < 1:
        p.error("--samples must be positive")
    results = run(args.rustc, args.jemalloc, args.samples)
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    summary(results)
