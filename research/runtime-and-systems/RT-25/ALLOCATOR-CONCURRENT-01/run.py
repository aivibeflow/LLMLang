"""Measure native allocator workload and capture scoped address-space pressure results."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
from random import Random
import resource
from statistics import median, quantiles
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
COMPAT = HERE.parents[1] / "PROTOTYPES" / "ALLOCATOR-COMPAT-01" / "probe.rs"
PROVIDERS = ("glibc", "jemalloc", "mimalloc", "gperftools", "google")
SIZES = (24, 96, 300, 1024, 4096, 32768, 65536)
CAPS_MIB = (96, 192)


def oracle(workers):
    positions = [(worker, ticket) for worker in range(workers) for ticket in range(1024)]
    sizes = [SIZES[(worker + ticket) % len(SIZES)] for worker, ticket in positions]
    tags = [(31 * worker + 13 * ticket) % 256 for worker, ticket in positions]
    return (len(positions), sum(sizes), sum((index + 1) * (1 + size + tag)
                                            for index, (size, tag) in enumerate(zip(sizes, tags, strict=True))))


def base_environment():
    return {key: value for key, value in os.environ.items()
            if key != "LD_PRELOAD" and not key.startswith(("TCMALLOC_", "MALLOC_", "MIMALLOC_", "GLIBC_TUNABLES"))}


def execute(input, environment, check=True, preexec=None):
    result = subprocess.run(input, text=True, capture_output=True, check=check, timeout=45,
                            env=environment, preexec_fn=preexec)
    if check and result.stderr:
        raise ValueError(result.stderr)
    return result


def stats(values):
    cuts = quantiles(values, n=10, method="inclusive")
    return {"median": median(values), "p10": cuts[0], "p90": cuts[-1], "n": len(values)}


def counters():
    return {key: int(value) for key, value in
            map(str.split, Path("/sys/fs/cgroup/cpu.stat").read_text().splitlines())}


def limited(executable, library, environment, cap):
    def set_cap():
        maximum = cap * 2**20
        resource.setrlimit(resource.RLIMIT_AS, (maximum, maximum))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    process = execute([executable, library, "address-limit"], environment, check=False, preexec=set_cap)
    if process.returncode != 0:
        lines = [line.strip() for line in process.stderr.splitlines() if line.strip()]
        return {"outcome": "process-failed", "returncode": process.returncode,
                "diagnostic": lines[-1] if lines else "", "cap_mib": cap}
    if process.stderr:
        raise ValueError(process.stderr)
    data = json.loads(process.stdout)
    if not (0 <= data["retained_chunks"] < 96 and data["bytes_per_chunk"] == 4 * 2**20):
        raise ValueError(data)
    return {"outcome": "allocation-refused", "cap_mib": cap, **data}


def measure(args, scratch):
    if args.trials < 2 or len(set(args.cpu)) < 2 or not set(args.cpu) <= os.sched_getaffinity(0):
        raise ValueError("need two available logical CPUs and repeated trials")
    os.sched_setaffinity(0, set(args.cpu))
    clean = base_environment()
    probe = scratch / "probe"
    execute([args.rustc, "--edition", "2021", "-O", "-D", "warnings", HERE / "probe.rs", "-o", probe], clean)
    paths = {name: getattr(args, name).resolve() for name in PROVIDERS}
    environments = {name: clean if name == "glibc" else {**clean, "LD_PRELOAD": str(path)}
                    for name, path in paths.items()}
    random = Random(args.seed)
    rows = []
    before = counters()
    for block in range(args.trials):
        ordered = [(workers, name) for workers in (1, 4) for name in PROVIDERS]
        random.shuffle(ordered)
        for position, (workers, name) in enumerate(ordered):
            proc = execute([probe, paths[name], "churn", str(workers)], environments[name])
            observed = json.loads(proc.stdout)
            if tuple(observed[key] for key in ("count", "payload_bytes", "checksum")) != oracle(workers):
                raise ValueError((name, workers, observed))
            rows.append({"block": block, "position": position, "provider": name, "producers": workers, **observed})
    after = counters()
    pressure = {name: [limited(probe, paths[name], environments[name], cap) for cap in CAPS_MIB]
                for name in PROVIDERS}
    metrics = ("elapsed_ns", "peak_kib", "after_drop_kib")
    summary = {f"{name}/{workers}": {key: stats([row[key] for row in rows
                                                   if (row["provider"], row["producers"]) == (name, workers)])
                for key in metrics} for name in PROVIDERS for workers in (1, 4)}
    return {
        "cpu": args.cpu, "cpu_model": next(line.split(":", 1)[1].strip()
             for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("model name")),
        "kernel": platform.release(), "python": platform.python_version(), "seed": args.seed, "trials": args.trials,
        "rustc": execute([args.rustc, "--version"], clean).stdout.strip(),
        "libraries": {name: {"filename": path.name, "sha256": sha256(path.read_bytes()).hexdigest()}
                      for name, path in paths.items()},
        "sources_sha256": {name: sha256(path.read_bytes()).hexdigest()
                           for name, path in (("run.py", HERE / "run.py"), ("probe.rs", HERE / "probe.rs"),
                                              ("compatibility_probe", COMPAT))},
        "counter_delta_churn_only": {key: after[key] - before[key] for key in before},
        "pressure": pressure, "samples": rows, "summary": summary,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in (*PROVIDERS, "rustc", "output"):
        parser.add_argument(f"--{option}", required=True, type=Path)
    parser.add_argument("--cpu", required=True, type=int, nargs=2)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--trials", required=True, type=int)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="rt25-concurrent-allocator-") as temp:
        evidence = measure(args, Path(temp))
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
