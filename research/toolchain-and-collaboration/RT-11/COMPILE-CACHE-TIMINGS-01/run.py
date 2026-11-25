"""Time clean, Make incremental, and exact content-keyed object builds."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
from random import Random
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter_ns

HERE = Path(__file__).resolve().parent
GROUPS, PER_GROUP = 3, 4
UNITS = GROUPS * PER_GROUP
STAGES = ("cold", "warm", "local", "component", "broad")
METHODS = ("clean", "incremental", "content")
EXPECTED = {"cold": 12, "warm": 0, "local": 1, "component": 4, "broad": 12}
FLAGS = ("--target=x86_64-pc-linux-gnu", "-std=c++17", "-O2", "-fno-ident")


def digest(data):
    return sha256(data).hexdigest()


def metadata(path):
    output = subprocess.check_output([path, "--version"], text=True).splitlines()[0]
    return {"version": output, "sha256": digest(path.read_bytes())}


def write_fixture(root):
    root.mkdir()
    (root / "obj").mkdir()
    (root / "shared.hpp").write_text("constexpr unsigned shared_value = 7u;\n")
    for group in range(GROUPS):
        (root / f"component{group}.hpp").write_text(f"constexpr unsigned component_value = {11 + group}u;\n")
    rules = ["all: " + " ".join(f"obj/unit{i}.o" for i in range(UNITS)), ""]
    for index in range(UNITS):
        component = f"component{index // PER_GROUP}.hpp"
        source = f"unit{index}.cpp"
        (root / source).write_text(
            f'#include "shared.hpp"\n#include "{component}"\n'
            f'extern "C" unsigned value_{index}(unsigned x) {{\n'
            f'    return (x + shared_value) * component_value + {index}u;\n'
            '}\n')
        rules.extend((f"obj/unit{index}.o: {source} shared.hpp {component}",
                      '\t@echo compile "$<"',
                      '\t@"$(CXX)" $(CXXFLAGS) -MMD -MP -c "$<" -o "$@"', ""))
    (root / "Makefile").write_text("\n".join(rules) + "\n-include $(wildcard obj/*.d)\n")


def apply(root, stage):
    if stage == "local":
        path = root / "unit0.cpp"
        path.write_text(path.read_text().replace("+ 0u;", "+ 1u;"))
    if stage == "component":
        (root / "component1.hpp").write_text("constexpr unsigned component_value = 29u;\n")
    if stage == "broad":
        (root / "shared.hpp").write_text("constexpr unsigned shared_value = 101u;\n")


def make_build(make, clang, root, fresh, env):
    argv = [make, "--no-print-directory", "-rR", "-j1"]
    if fresh:
        argv.append("-B")
    result = subprocess.run([*argv, f"CXX={clang}", "CXXFLAGS=" + " ".join(FLAGS), "all"],
                            cwd=root, capture_output=True, check=True, text=True, timeout=60, env=env)
    return sum(line.startswith("compile ") for line in result.stdout.splitlines()), 0, None


def cached_build(clang, compiler, root, cache, env):
    compiled = hits = key_and_lookup_ns = 0
    for index in range(UNITS):
        source = f"unit{index}.cpp"
        output = root / "obj" / f"unit{index}.o"
        inputs = (source, "shared.hpp", f"component{index // PER_GROUP}.hpp")
        start = perf_counter_ns()
        key = digest(json.dumps({
            "inputs": [(name, digest((root / name).read_bytes())) for name in inputs],
            "toolchain": compiler, "argv": [*FLAGS, "-MMD", "-MP"], "output": str(output.relative_to(root)),
            "environment": {"LC_ALL": "C", "TZ": "UTC", "SOURCE_DATE_EPOCH": "0"},
        }, sort_keys=True).encode())
        entry = cache.get(key)
        if entry is not None:
            expected, artifact = entry
            assert digest(artifact) == expected
            if not output.exists() or digest(output.read_bytes()) != expected:
                output.write_bytes(artifact)
            hits += 1
        key_and_lookup_ns += perf_counter_ns() - start
        if entry is None:
            subprocess.run([clang, *FLAGS, "-MMD", "-MP", "-c", source, "-o", str(output.relative_to(root))],
                           cwd=root, capture_output=True, check=True, timeout=30, env=env)
            artifact = output.read_bytes()
            cache[key] = (digest(artifact), artifact)
            compiled += 1
    return compiled, hits, key_and_lookup_ns


def benchmark(clang, make, trials, seed):
    rng = Random(seed)
    compiler, make_tool = metadata(clang), metadata(make)
    assert compiler["version"] == "Debian clang version 19.1.7 (3+b1)"
    env = {**os.environ, "LC_ALL": "C", "TZ": "UTC", "SOURCE_DATE_EPOCH": "0"}
    env.pop("MAKEFLAGS", None)
    env.pop("MFLAGS", None)
    cpu = next(line.partition(":")[2].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
               if line.startswith("model name"))
    host = {"linux": platform.release(), "arch": platform.machine(), "python": platform.python_version(),
            "logical_cpu": os.cpu_count(), "cpu_name": cpu,
            "clock": "perf_counter_ns", "parallel_jobs": 1, "affinity": sorted(os.sched_getaffinity(0))}
    rows = []
    with TemporaryDirectory(prefix="llmlang-compile-cache-timing-") as scratch:
        for trial in range(trials):
            parent = Path(scratch) / str(trial)
            parent.mkdir()
            roots = {method: parent / method for method in METHODS}
            for root in roots.values():
                write_fixture(root)
            cache = {}
            for stage in STAGES:
                order = list(METHODS)
                rng.shuffle(order)
                observed = {}
                for position, method in enumerate(order):
                    root = roots[method]
                    apply(root, stage)
                    start = perf_counter_ns()
                    if method == "content":
                        counts = cached_build(clang, compiler, root, cache, env)
                    else:
                        counts = make_build(make, clang, root, method == "clean", env)
                    duration = perf_counter_ns() - start
                    compiled, hits, key_ns = counts
                    assert compiled == (UNITS if method == "clean" else EXPECTED[stage]), (method, stage, compiled)
                    assert hits == (UNITS - compiled if method == "content" else 0)
                    output = [(name.name, digest(name.read_bytes())) for name in sorted((root / "obj").glob("*.o"))]
                    assert len(output) == UNITS
                    observed[method] = digest(json.dumps(output).encode())
                    rows.append({"trial": trial, "stage": stage, "method": method, "order": position,
                                 "elapsed_ns": duration, "compiler_invocations": compiled, "cache_hits": hits,
                                 "key_lookup_verify_materialize_ns": key_ns, "manifest_sha256": observed[method]})
                assert len(set(observed.values())) == 1, (stage, trial, observed)
    return {
        "schema": "rt11-synthetic-cxx-compile-cache-timing-v1", "repetitions": trials, "order_seed": seed,
        "translation_units": UNITS, "groups": GROUPS, "compile_flags": FLAGS, "input_shape": list(STAGES),
        "host": host, "toolchain": {"clang": compiler, "make": make_tool},
        "source_sha256": digest((HERE / "run.py").read_bytes()), "samples": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", type=Path, required=True)
    parser.add_argument("--make", type=Path, default=Path("/usr/bin/make"))
    parser.add_argument("--trials", type=int, default=7)
    parser.add_argument("--seed", type=int, default=318)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.clang.resolve(), args.make.resolve(), args.trials, args.seed),
                     indent=2, sort_keys=True))
