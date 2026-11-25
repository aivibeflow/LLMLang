"""Replay the pinned RT-25 graph and compatibility probes with four providers."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path

BASELINE = "9b710959a056ab0222812a6061eab08c65129fec"
ROOT = Path("research/runtime-and-systems/PROTOTYPES")
GRAPH = ROOT / "ALLOCATOR-BENCH-01/graph.rs"
PROBE = ROOT / "ALLOCATOR-COMPAT-01/probe.rs"
ARCHIVE = ROOT / "ALLOCATOR-BENCH-01/results-linux-x86_64.json"
BUILD_FLAGS = ["--edition=2024", "-C", "opt-level=3", "-D", "warnings"]
EXPECTED_PROBE = "3200 Rust allocation sequences and C resize-failure check passed"


def output(*args):
    return subprocess.check_output(args, text=True).strip()


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_source(path):
    pinned = subprocess.check_output(["git", "show", f"{BASELINE}:{path}"])
    if path.read_bytes() != pinned:
        raise ValueError(f"{path} differs from {BASELINE}")
    return hashlib.sha256(pinned).hexdigest()


def run_process(executable, library, cpu, preload):
    environment = {
        name: value for name, value in os.environ.items()
        if not name.startswith(("MIMALLOC_", "TCMALLOC_", "MALLOC_"))
        and name not in {"LD_PRELOAD", "GLIBC_TUNABLES"}
    }
    environment["LC_ALL"] = "C"
    if preload:
        environment["LD_PRELOAD"] = str(library.absolute())
    return subprocess.check_output(
        ["taskset", "-c", str(cpu), str(executable), library.name],
        text=True, env=environment, timeout=30,
    ).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rustc", type=Path, required=True)
    parser.add_argument("--glibc", type=Path, required=True)
    parser.add_argument("--jemalloc", type=Path, required=True)
    parser.add_argument("--tcmalloc", type=Path, required=True)
    parser.add_argument("--mimalloc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    sources = {str(path): check_source(path) for path in (GRAPH, PROBE, ARCHIVE)}
    archived = json.loads(ARCHIVE.read_text())
    archived_checksums = {row["checksum"] for row in archived["samples"]}
    providers = {name: getattr(args, name) for name in ("glibc", "jemalloc", "tcmalloc", "mimalloc")}
    library_records = {
        name: {"filename": library.name, "sha256": sha256(library)}
        for name, library in providers.items()
    }
    cpu = min(os.sched_getaffinity(0))
    cpu_name = next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                    if line.startswith("model name"))
    # The four orders balance both position and immediate predecessor.
    orders = ((0, 1, 3, 2), (1, 2, 0, 3), (2, 3, 1, 0), (3, 0, 2, 1))
    names = list(providers)
    with tempfile.TemporaryDirectory(prefix="llmlang-allocator-replay-") as temporary:
        graph = Path(temporary) / "graph"
        probe = Path(temporary) / "probe"
        for source, executable in ((GRAPH, graph), (PROBE, probe)):
            subprocess.run(
                [args.rustc, *BUILD_FLAGS, source, "-o", executable],
                env=os.environ | {"LC_ALL": "C"}, check=True, timeout=60,
            )
        for name, library in providers.items():
            line = run_process(probe, library, cpu, preload=name != "glibc")
            actual_library, message = line.rsplit(": ", 1)
            bound = Path(actual_library)
            if bound.name != library.name or sha256(bound) != library_records[name]["sha256"]:
                raise ValueError(f"unexpected bound allocator: {actual_library}")
            if message != EXPECTED_PROBE:
                raise ValueError(f"unexpected compatibility probe result: {line}")
            library_records[name]["compatibility"] = message

        samples = []
        for block, order in enumerate(orders * 3, start=1):
            for position, index in enumerate(order, start=1):
                name = names[index]
                line = run_process(graph, providers[name], cpu, preload=name != "glibc")
                samples.append({"block": block, "position": position, "provider": name, **json.loads(line)})

    checksums = {row["checksum"] for row in samples}
    if len(checksums) != 1 or checksums != archived_checksums:
        raise ValueError(f"graph checksum differs from archive: {checksums} vs {archived_checksums}")
    result = {
        "source_revision": BASELINE,
        "source_sha256": sources,
        "host": platform.platform(),
        "cpu": cpu_name,
        "available_cpus": sorted(os.sched_getaffinity(0)),
        "pinned_cpu": cpu,
        "cpu_quota_period": Path("/sys/fs/cgroup/cpu.max").read_text().strip(),
        "python": platform.python_version(),
        "rustc": output(args.rustc, "--version", "--verbose").splitlines(),
        "cc": output("cc", "--version").splitlines()[0],
        "binutils": output("ld", "--version").splitlines()[0],
        "taskset": output("taskset", "--version"),
        "build_flags": BUILD_FLAGS,
        "providers": library_records,
        "sample_count_per_provider": 12,
        "samples": samples,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
