"""Collect matched LLVM ORC and Cranelift ready-to-call observation samples."""

import argparse
import csv
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
from random import Random
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "cranelift-checked-add"))
from run import SOURCE, cases, compile_source, lower, reference


CASES = ((3, 1, 1), (0x7fffffff, 1, 1), (7, 5, 0), (4, 3, 2))
PROFILES = ("llvm-O0", "llvm-O3", "cranelift-none", "cranelift-speed")


def check_output(output, samples, expected):
    lines = output.splitlines()
    if len(lines) != samples * (1 + len(expected)):
        raise ValueError(f"Expected complete timing and observation records: {output}")
    timings = []
    for i in range(samples):
        first = i * (1 + len(expected))
        label, sequence, nanos = lines[first].split()
        if label != "time" or int(sequence) != i or int(nanos) <= 0:
            raise ValueError(lines[first])
        observations = [line.split() for line in lines[first + 1:first + 1 + len(expected)]]
        if observations != expected:
            raise ValueError(f"JIT observation mismatch: {observations!r}")
        timings.append(int(nanos))
    return timings


def checked_command(command, cpu):
    prefix = ["taskset", "-c", str(cpu)]
    proc = subprocess.run(prefix + list(map(str, command)), text=True, capture_output=True,
                          check=True, timeout=60)
    if proc.stderr:
        raise ValueError(proc.stderr)
    return proc.stdout


def expected_rows(program, vectors):
    result = []
    for vector in vectors:
        observed = reference(program, vector)
        result.append(["check", str(observed["status"]), str(observed["out_slot"]),
                       *map(str, observed["effects"])])
    return result


def cpu_counters():
    stat = Path("/sys/fs/cgroup/cpu.stat")
    return {key: int(value) for key, value in map(str.split, stat.read_text().splitlines())} if stat.exists() else {}


def collect(args):
    if args.cpu not in os.sched_getaffinity(0):
        raise ValueError(f"CPU {args.cpu} is outside the runner affinity")
    program = compile_source(SOURCE.replace("operation", "checked_sadd"))
    expected = expected_rows(program, CASES)
    suite = cases()
    suite_expected = expected_rows(program, suite)
    ir = lower((program,)).encode()
    inputs = {str(path.relative_to(HERE.parent)): sha256(path.read_bytes()).hexdigest()
              for path in (HERE / "run.py", HERE / "orc.cpp", HERE / "src/main.rs",
                           HERE.parent / "cranelift-checked-add/src/main.rs",
                           HERE / "Cargo.toml", HERE / "Cargo.lock")}
    inputs["checked_add.ll"] = sha256(ir).hexdigest()
    rng = Random(args.seed)
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="llmlang-jit-materialization-") as scratch:
        ir_path = Path(scratch) / "input.ll"
        ir_path.write_bytes(ir)
        commands = {
            "llvm-O0": [args.orc, "0", args.samples, ir_path],
            "llvm-O3": [args.orc, "3", args.samples, ir_path],
            "cranelift-none": [args.cranelift, "none", args.samples],
            "cranelift-speed": [args.cranelift, "speed", args.samples],
        }
        recheck = Path(scratch) / "vectors.txt"
        recheck.write_text("".join(f"{a} {b} {enabled}\n" for a, b, enabled in suite))
        for level in ("0", "3"):
            output = checked_command([args.orc, level, 1, ir_path, recheck], args.cpu)
            check_output(output, 1, suite_expected)

        rows = []
        before = cpu_counters()
        for batch in range(args.batches):
            order = list(PROFILES)
            rng.shuffle(order)
            for position, profile in enumerate(order):
                output = checked_command(commands[profile], args.cpu)
                timings = check_output(output, args.samples, expected)
                rows.extend((args.seed, batch, position, profile, i, time)
                            for i, time in enumerate(timings))

    after = cpu_counters()
    with (args.output / "samples.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("seed", "batch", "position", "profile", "sample", "elapsed_ns"))
        writer.writerows(rows)
    cpu_model = next(line.partition(":")[2].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                     if line.startswith("model name"))
    gate = Path("/sys/fs/cgroup/cpu.max")
    configuration = {"cpu": args.cpu, "cpu_model": cpu_model, "quota": gate.read_text().strip() if gate.exists() else None,
                     "kernel": platform.release(), "machine": platform.machine(), "batches": args.batches,
                     "samples": args.samples, "seed": args.seed, "oracle_checks_per_sample": len(expected),
                     "untimed_orc_checks_per_profile": len(suite),
                     "cgroup_counter_delta": {key: value - before[key] for key, value in after.items()
                                              if key in before},
                     "source_inputs_sha256": inputs, "probe_sha256": {
                         "orc": sha256(args.orc.read_bytes()).hexdigest(),
                         "cranelift": sha256(args.cranelift.read_bytes()).hexdigest(),
                     }}
    (args.output / "config.json").write_text(json.dumps(configuration, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orc", type=Path, required=True)
    parser.add_argument("--cranelift", type=Path, required=True)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--batches", type=int, default=24)
    parser.add_argument("--samples", type=int, default=31)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if min(args.batches, args.samples) < 2:
        parser.error("At least two batches and samples are needed")
    collect(args)
