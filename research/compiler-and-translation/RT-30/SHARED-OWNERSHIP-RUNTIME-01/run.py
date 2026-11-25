"""Compare mixed-language handle traces and selectively rebuild exactly one adapter."""

import argparse
from collections import Counter
import ctypes
from hashlib import sha256
from itertools import permutations, product
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
ADAPTERS = ("c", "cpp", "go", "rust")
CREATE, TRANSFER, READ, RELEASE = range(4)
FIXTURES = ("runtime.h", "runtime.c", "adapter.c", "adapter.cc", "adapter.go", "adapter.rs",
            "measure.c", "run.py")


def command(args, directory=None, extra_env=None):
    env = {**os.environ, "LC_ALL": "C", "TZ": "UTC", "SOURCE_DATE_EPOCH": "1764000000"}
    env.update(extra_env or {})
    return subprocess.run(
        args, cwd=directory, env=env, text=True, capture_output=True, check=True, timeout=120,
    ).stdout.strip()


def hash_file(path):
    return sha256(path.read_bytes()).hexdigest()


def build(args, work):
    for name in FIXTURES[:-2]:
        shutil.copyfile(HERE / name, work / name)
    provider = work / "libowned.so"
    command([
        args.cc, "-std=c17", "-O2", "-fPIC", "-shared", "-Wall", "-Wextra", "-Werror",
        "-Wl,-soname,libowned.so", "runtime.c", "-o", provider,
    ], work)
    outputs = {name: work / f"lib{name}.so" for name in ADAPTERS}
    for name, compiler, extension, standard in (
        ("c", args.cc, "c", "c17"), ("cpp", args.cxx, "cc", "c++20"),
    ):
        command([
            compiler, f"-std={standard}", "-O2", "-fPIC", "-shared", "-Wall", "-Wextra", "-Werror",
            "-Wl,--no-undefined", f"adapter.{extension}", "-L.", "-lowned", "-o", outputs[name],
        ], work)
    command([
        args.rustc, "--edition=2021", "--crate-name=ownership_probe", "--crate-type=cdylib",
        "-Copt-level=2", "-Cdebuginfo=0", "--remap-path-prefix", f"{work}=/fixture",
        "-L", "native=.", "adapter.rs", "-o", outputs["rust"],
    ], work)

    golang = work / "golang"
    golang.mkdir()
    for name in ("adapter.go", "runtime.h", "libowned.so"):
        shutil.copyfile(work / name, golang / name)
    (golang / "go.mod").write_text("module llmlang.local/ownership\n\ngo 1.23\n", encoding="utf-8")
    go_env = {
        "GOCACHE": str(args.go_cache.resolve()), "CGO_ENABLED": "1", "CC": args.cc,
        "GOTOOLCHAIN": "local", "GOOS": "linux", "GOARCH": "amd64", "GOAMD64": "v1",
        "GOENV": "off", "GOPROXY": "off", "GOSUMDB": "off", "GOMAXPROCS": "2",
        "GOFLAGS": "", "GOWORK": "off",
    }
    command([
        args.go, "build", "-p", "2", "-mod=readonly", "-buildvcs=false", "-trimpath",
        "-buildmode=c-shared", "-ldflags=-buildid=", "-o", outputs["go"], ".",
    ], golang, go_env)
    mutated = work / "libcpp-rebuilt.so"
    command([
        args.cxx, "-std=c++20", "-O2", "-fPIC", "-shared", "-Wall", "-Wextra", "-Werror",
        "-DALTER_TRANSFER", "-Wl,--no-undefined", "adapter.cc", "-L.", "-lowned", "-o", mutated,
    ], work)
    return provider, outputs, mutated


def footprint(path):
    stripped = path.with_name(path.stem + "-without-debug.so")
    command(["strip", "--strip-debug", "-o", stripped, path])
    dynamic = command(["readelf", "-dW", path])
    sections = command(["size", "-A", path])
    return {
        "elf_sha256": hash_file(path), "elf_bytes": path.stat().st_size,
        "debug_stripped_bytes": stripped.stat().st_size,
        "needed": re.findall(r"\(NEEDED\).*\[([^]]+)\]", dynamic),
        "sections_bytes": {
            parts[0]: int(parts[1]) for line in sections.splitlines()
            if (parts := line.split()) and parts[0] in (".text", ".rodata", ".data", ".bss")
        },
    }


def unpack(word):
    return word >> 24, (word >> 8) & 65535, word & 255


class SourceOwnership:
    def __init__(self):
        self.serial = 0
        self.live = None

    def apply(self, request):
        operation, actor, peer, handle, payload = request
        valid = actor in range(4) and operation in range(4)
        valid &= operation != TRANSFER or peer in range(4)
        valid &= operation != CREATE or payload in range(256)
        if not valid:
            return (1, 0, 0)
        if operation == CREATE:
            if self.live is not None:
                return (2, 0, 0)
            if self.serial == 65535:
                return (5, 0, 0)
            self.serial += 1
            self.live = actor, payload
            return (0, self.serial, payload)
        if self.live is None or handle != self.serial:
            return (3, 0, 0)
        owner, payload = self.live
        if actor != owner:
            return (4, 0, 0)
        if operation == RELEASE:
            self.live = None
            return (0, self.serial, 0)
        if operation == TRANSFER:
            self.live = peer, payload
        return (0, self.serial, payload)

    def snapshot(self):
        if self.live is None:
            return 0, self.serial, 0
        owner, payload = self.live
        return owner + 1, self.serial, payload


def native_functions(provider, outputs):
    runtime = ctypes.CDLL(str(provider), mode=ctypes.RTLD_GLOBAL)
    runtime.rt_reset.argtypes = []
    runtime.rt_reset.restype = None
    runtime.rt_snapshot.argtypes = []
    runtime.rt_snapshot.restype = ctypes.c_uint32
    functions = {}
    for name, path in outputs.items():
        step = ctypes.CDLL(str(path)).step
        step.argtypes = [ctypes.c_uint32] * 5
        step.restype = ctypes.c_uint32
        functions[name] = step
    return runtime, functions


def mixed_cases(runtime, functions):
    counts = Counter()
    trace = sha256()
    for route, (owner, recipient), value in product(
        permutations(ADAPTERS), permutations(range(4), 2), (0, 1, 127, 255),
    ):
        a, b, c, d = route
        steps = (
            (a, (CREATE, owner, 0, 0, value)),
            (b, (CREATE, recipient, 0, 0, value)),
            (b, (TRANSFER, owner, 5, 1, 0)),
            (b, (TRANSFER, owner, recipient, 1, 0)),
            (c, (READ, owner, 0, 1, 0)),
            (c, (READ, recipient, 0, 1, 0)),
            (d, (RELEASE, recipient, 0, 1, 0)),
            (a, (CREATE, owner, 0, 0, value ^ 255)),
            (b, (READ, owner, 0, 1, 0)),
            (c, (READ, owner, 0, 2, 0)),
            (d, (RELEASE, owner, 0, 2, 0)),
        )
        counts["scenarios"] += 1
        runtime.rt_reset()
        oracle = SourceOwnership()
        for adapter, request in steps:
            expected = (oracle.apply(request), oracle.snapshot())
            observed = (unpack(functions[adapter](*request)), unpack(runtime.rt_snapshot()))
            counts["steps"] += 1
            counts["result_mismatches"] += observed[0] != expected[0]
            counts["state_mismatches"] += observed[1] != expected[1]
            counts["complete_mismatches"] += observed != expected
            trace.update(json.dumps([adapter, request, observed], separators=(",", ":")).encode())
    return {**counts, "trace_sha256": trace.hexdigest()}


def exhausted_generation(runtime, functions):
    oracle = SourceOwnership()
    c, cpp, go, rust = (functions[name] for name in ADAPTERS)
    runtime.rt_reset()
    for generation in range(1, 65536):
        for adapter, request in (
            (c, (CREATE, 0, 0, 0, generation % 256)),
            (cpp, (RELEASE, 0, 0, generation, 0)),
        ):
            assert unpack(adapter(*request)) == oracle.apply(request)
    for adapter, request in (
        (go, (CREATE, 1, 0, 0, 255)), (rust, (READ, 0, 0, 1, 0)),
    ):
        assert unpack(adapter(*request)) == oracle.apply(request)
    assert unpack(runtime.rt_snapshot()) == oracle.snapshot() == (0, 65535, 0)
    return {"operations": 131072, "last_handle": 65535, "wraparound": "refused"}


def timed(args, work, provider, outputs):
    observer = work / "measure"
    command([args.cc, "-std=c17", "-O2", "-Wall", "-Wextra", "-Werror",
             HERE / "measure.c", "-ldl", "-o", observer])
    rows = command([observer, provider, *outputs.values()]).splitlines()
    observations = {name: [] for name in ADAPTERS}
    for row in rows:
        trial, index, iterations, elapsed, checksum = map(int, row.split())
        observations[ADAPTERS[index]].append({
            "round": trial, "calls": iterations, "wall_ns": elapsed, "checksum": checksum,
        })
    assert all(len(rows) == 7 for rows in observations.values())
    return {
        "clock": "CLOCK_MONOTONIC_RAW", "host": os.uname().machine,
        "kernel": os.uname().release, "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "rounds": observations,
    }


def collect(args, work):
    provider, outputs, mutated = build(args, work)
    runtime, functions = native_functions(provider, outputs)
    baseline = mixed_cases(runtime, functions)
    wraparound = exhausted_generation(runtime, functions)
    assert baseline["scenarios"] == 1152 and baseline["steps"] == 12672
    assert baseline["complete_mismatches"] == 0

    providers = {name: footprint(path) for name, path in outputs.items()}
    assert all("libowned.so" in row["needed"] for row in providers.values())
    substituted = {**outputs, "cpp": mutated}
    runtime, changed_functions = native_functions(provider, substituted)
    changed = mixed_cases(runtime, changed_functions)
    assert changed["complete_mismatches"] > 0
    assert changed["trace_sha256"] != baseline["trace_sha256"]
    changed_footprint = footprint(mutated)
    assert changed_footprint["elf_sha256"] != providers["cpp"]["elf_sha256"]
    assert changed_footprint["needed"] == providers["cpp"]["needed"]
    assert all(hash_file(path) == providers[name]["elf_sha256"] for name, path in outputs.items())
    if args.timing:
        args.timing.write_text(json.dumps(timed(args, work, provider, outputs), indent=2) + "\n")
    return {
        "tools": {
            "cc": command([args.cc, "--version"]).splitlines()[0],
            "cxx": command([args.cxx, "--version"]).splitlines()[0],
            "go": command([args.go, "version"]),
            "rustc": command([args.rustc, "--version"]),
        },
        "sources": {name: hash_file(HERE / name) for name in FIXTURES},
        "runtime": footprint(provider), "adapters": providers,
        "native_baseline": baseline, "generation_refusal": wraparound,
        "changed_adapter_only": {"cpp": changed_footprint, "observations": changed},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, tool in (("cc", "gcc"), ("cxx", "g++"), ("go", "go"), ("rustc", "rustc")):
        parser.add_argument(f"--{name}", default=tool)
    parser.add_argument("--go-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timing", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt30-owned-") as directory:
        evidence = collect(args, Path(directory))
    args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n")
