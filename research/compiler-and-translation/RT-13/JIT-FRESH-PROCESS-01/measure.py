"""Collect scoped paired fresh-process JIT measurements and validate every result."""

import argparse
import csv
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import platform
from random import Random
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
MATERIALIZATION = HERE.parent / "JIT-MATERIALIZATION-01"
spec = spec_from_file_location("materialization_fixture", MATERIALIZATION / "run.py")
materialization_fixture = module_from_spec(spec)
spec.loader.exec_module(materialization_fixture)


def run(*command):
    result = subprocess.run(command, capture_output=True, check=True, text=True, timeout=30)
    if result.stderr:
        raise ValueError(result.stderr)
    return result.stdout


def collect(args, scratch):
    os.sched_setaffinity(0, {args.cpu})
    fixture = materialization_fixture
    program = fixture.compile_source(fixture.SOURCE.replace("operation", "checked_sadd"))
    expected = fixture.expected_rows(program, fixture.CASES)
    ir = scratch / "probe.ll"
    ir.write_text(fixture.lower((program,)))
    probes = {
        "llvm-O0": (args.orc, "0", "1", ir),
        "llvm-O3": (args.orc, "3", "1", ir),
        "cranelift-none": (args.cranelift, "none", "1"),
        "cranelift-speed": (args.cranelift, "speed", "1"),
    }
    # Prime common executable and shared-library pages. Each actual sample starts a fresh child.
    for command in probes.values():
        run(args.wrapper, *command)
    random = Random(args.seed)
    counters = fixture.cpu_counters()
    rows = []
    for batch in range(args.batches):
        order = list(probes)
        random.shuffle(order)
        for position, name in enumerate(order):
            report = run(args.wrapper, *probes[name])
            parts = report.splitlines()
            materialization, = fixture.check_output("\n".join(parts[:-1]), 1, expected)
            label, elapsed, peak_kib = parts[-1].split()
            elapsed, peak_kib = int(elapsed), int(peak_kib)
            if label != "process" or elapsed <= materialization or peak_kib <= 0:
                raise ValueError(report)
            rows.append((batch, position, name, elapsed, materialization, peak_kib))
    after = fixture.cpu_counters()
    with (args.output / "samples.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("batch", "position", "profile", "process_ns", "jit_ns", "child_peak_kib"))
        writer.writerows(rows)

    executable = {}
    for name, path in (("llvm-orc", args.orc), ("cranelift", args.cranelift), ("wrapper", args.wrapper)):
        executable[name] = {
            "bytes": path.stat().st_size,
            "sha256": sha256(path.read_bytes()).hexdigest(),
            "dt_needed": [
                line.split("[", 1)[1].split("]", 1)[0] for line in run("readelf", "-d", path).splitlines()
                if "(NEEDED)" in line
            ],
        }
    sources = (HERE / "process.c", HERE / "measure.py", MATERIALIZATION / "orc.cpp",
               MATERIALIZATION / "src/main.rs", MATERIALIZATION / "run.py", MATERIALIZATION / "Cargo.lock",
               HERE.parent / "cranelift-checked-add/run.py", HERE.parent / "cranelift-checked-add/src/main.rs")
    result = {
        "batches": args.batches, "seed": args.seed, "cpu": args.cpu, "machine": platform.machine(),
        "cpu_model": next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                          if line.startswith("model name")),
        "kernel": platform.release(), "cpu_limit": Path("/sys/fs/cgroup/cpu.max").read_text().strip(),
        "deltas": {key: value - counters[key] for key, value in after.items() if key in counters},
        "load_average": os.getloadavg(), "oracle_rows_per_sample": len(expected), "executables": executable,
        "sources_sha256": {str(path.relative_to(HERE.parent)): sha256(path.read_bytes()).hexdigest()
                           for path in sources},
        "lowered_ir_sha256": sha256(ir.read_bytes()).hexdigest(),
        "tools": {tool: run(*command).splitlines()[0] for tool, command in {
            "gcc": ("cc", "-dumpfullversion"), "llvm": ("llvm-config-19", "--version"),
            "rust": ("rustc", "--version"), "glibc": ("getconf", "GNU_LIBC_VERSION"),
            "python": (sys.executable, "--version"),
        }.items()},
    }
    (args.output / "config.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("orc", "cranelift", "wrapper", "output"):
        parser.add_argument(f"--{option}", type=Path, required=True)
    for option in ("cpu", "batches", "seed"):
        parser.add_argument(f"--{option}", type=int, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    if args.cpu not in os.sched_getaffinity(0) or args.batches < 1:
        parser.error("CPU outside current affinity or invalid batch count")
    with TemporaryDirectory(prefix="llmlang-jit-fresh-process-") as temp:
        collect(args, Path(temp))
