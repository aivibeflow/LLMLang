"""Measure the shared receiver runtime and adapter calls in a native C process."""

import argparse
from collections import Counter
import csv
import ctypes
from hashlib import sha256
import importlib.util
from itertools import product
import json
import os
from pathlib import Path
import platform
from random import Random
import struct
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parents[1] / "RT-30" / "SHARED-C-RUNTIME-01"
SPEC = importlib.util.spec_from_file_location("checked_receiver_runtime", RUNTIME / "run.py")
RUNTIME_TOOLS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME_TOOLS)
VECTOR_COUNT = 256
MASK = 2**64 - 1


def encode(result):
    status, state, events = result
    trace = int("".join(str(event) for event in events), 16)
    return status << 48 | trace << 32 | state


def expected_checksum(cases, repetitions):
    return sum(encode(RUNTIME_TOOLS.oracle(case)) for case in cases) * repetitions & MASK


def profiles():
    valid = [(index % 2, 128 + index % 32, index % 31 - 15, 3)
             for index in range(VECTOR_COUNT)]
    full = tuple(product((0, 1, 2, RUNTIME_TOOLS.MAX_U32), RUNTIME_TOOLS.STATES,
                         RUNTIME_TOOLS.CHANGES, RUNTIME_TOOLS.GRANTS))
    dispersed = Random(331).sample(full, VECTOR_COUNT)
    return {"all-success": valid, "mixed-status": dispersed}


def use_symbol(binary, name):
    library = ctypes.CDLL(str(binary))
    symbol = getattr(library, name)
    symbol.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_int32, ctypes.c_uint32]
    symbol.restype = ctypes.c_uint64
    return symbol


def prepare_native(args, work):
    archive = RUNTIME_TOOLS.build_archive(args, work)
    provider = work / "provider.so"
    RUNTIME_TOOLS.execute([args.cc, "-shared", "-Wl,--no-undefined",
                           "-Wl,--whole-archive", str(archive), "-Wl,--no-whole-archive",
                           "-o", str(provider)], work)
    binaries = {"native-runtime": (provider, "rt_dispatch")}
    for profile in RUNTIME_TOOLS.ADAPTER:
        binary = RUNTIME_TOOLS.build_adapter(args, work / profile, profile, archive)
        binaries[profile] = binary, "probe"
    harness = work / "measure"
    RUNTIME_TOOLS.execute([args.cc, "-std=c17", "-O3", "-Wall", "-Wextra", "-Werror",
                           str(HERE / "measure.c"), "-ldl", "-o", str(harness)], work)
    return archive, binaries, harness


def record(args, work):
    archive, binaries, harness = prepare_native(args, work)
    shapes = profiles()
    expected = {}
    workload = {}
    for name, cases in shapes.items():
        responses = tuple(RUNTIME_TOOLS.oracle(case) for case in cases)
        for profile, (binary, symbol) in binaries.items():
            observe = use_symbol(binary, symbol)
            if tuple(RUNTIME_TOOLS.observed(observe(*case)) for case in cases) != responses:
                raise AssertionError((name, profile))
        data = b"".join(struct.pack("<IIiI", *case) for case in cases)
        path = work / f"{name}.bin"
        path.write_bytes(data)
        expected[name] = (path, expected_checksum(cases, 16384 // VECTOR_COUNT),
                          expected_checksum(cases, args.calls // VECTOR_COUNT))
        workload[name] = {
            "input_sha256": sha256(data).hexdigest(),
            "native_records_checked_before_measurement": len(cases) * len(binaries),
            "statuses": dict(sorted(Counter(row[0] for row in responses).items())),
            "warmup_checksum": expected[name][1], "timed_checksum": expected[name][2],
        }

    cpus = os.sched_getaffinity(0)
    cpu = min(cpus) if args.cpu is None else args.cpu
    if cpu not in cpus:
        raise ValueError((cpu, sorted(cpus)))
    orders = list(product(shapes, binaries))
    random = Random(316)
    measured = []
    for trial in range(1, args.trials + 1):
        random.shuffle(orders)
        for order, (name, profile) in enumerate(orders, start=1):
            library, symbol = binaries[profile]
            path, warmup, timed = expected[name]
            stdout = RUNTIME_TOOLS.execute(
                [args.taskset, "-c", str(cpu), str(harness), str(library), symbol,
                 str(path), str(args.calls)], work, flags={"GOMAXPROCS": "1"},
            ).stdout
            elapsed, actual_warmup, actual_timed = map(int, stdout.split())
            if (actual_warmup, actual_timed) != (warmup, timed) or elapsed <= 0:
                raise AssertionError((name, profile, stdout))
            measured.append({"trial": trial, "order": order, "workload": name, "adapter": profile,
                             "calls": args.calls, "elapsed_ns": elapsed, "checksum": actual_timed})

    sources = [HERE / "run.py", HERE / "measure.c", RUNTIME / "run.py",
               RUNTIME / "runtime.h", RUNTIME / "runtime.c", *sorted(RUNTIME.glob("adapter.*.in"))]
    cpu_name = next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                    if line.startswith("model name"))
    receipt = {
        "machine": platform.machine(), "kernel": platform.release(),
        "cpu": cpu, "cpu_name": cpu_name, "clock": "CLOCK_MONOTONIC_RAW", "gomaxprocs": 1,
        "toolchain": {tool: RUNTIME_TOOLS.execute(
            [getattr(args, tool), "version" if tool == "go" else "--version"], work,
        ).stdout.splitlines()[0] for tool in ("cc", "cxx", "go", "rustc")},
        "archive_sha256": RUNTIME_TOOLS.digest(archive),
        "calls_per_trial": args.calls, "warmup_calls": 16384,
        "checked_workloads": workload,
        "source_sha256": {path.relative_to(HERE.parents[3]).as_posix(): RUNTIME_TOOLS.digest(path)
                          for path in sources},
    }
    return receipt, measured


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option, default in (("cc", "gcc"), ("cxx", "g++"), ("rustc", "rustc"), ("go", "go"),
                            ("ar", "ar"), ("taskset", "taskset")):
        parser.add_argument(f"--{option}", default=default)
    parser.add_argument("--go-cache", type=Path, required=True)
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--trials", type=int, default=7)
    parser.add_argument("--calls", type=int, default=524288)
    args = parser.parse_args()
    if args.calls <= 0 or args.calls % VECTOR_COUNT or args.trials < 1:
        parser.error("--calls must be a positive multiple of 256 and --trials at least one")
    with TemporaryDirectory(prefix="llmlang-native-dispatch-") as directory:
        receipt, measurements = record(args, Path(directory))
    with args.samples.open("w", newline="") as output:
        csv_writer = csv.DictWriter(output, fieldnames=tuple(measurements[0]), lineterminator="\n")
        csv_writer.writeheader()
        csv_writer.writerows(measurements)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
