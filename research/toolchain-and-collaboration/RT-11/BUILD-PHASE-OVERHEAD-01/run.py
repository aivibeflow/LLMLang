#!/usr/bin/env python3
"""Measure distinct warm build phases without treating isolated times as end-to-end latency."""

import argparse
from collections import defaultdict
from hashlib import sha256
from heapq import heapify, heappop, heappush
import json
import os
from pathlib import Path
import platform
import random
import shutil
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter_ns

ENV = {**os.environ, "LC_ALL": "C", "SOURCE_DATE_EPOCH": "0"}
PHASES = ("discovery", "hashing", "scheduling", "storage", "verification")
FLAGS = ("-std=c17", "-O2", "-Wall", "-Wextra", "-Werror")
SIZES = (2, 8, 24)


def command(args, root):
    result = subprocess.run(args, cwd=root, env=ENV, check=True, capture_output=True, timeout=30)
    return result.stdout


def digest(raw):
    return sha256(raw).hexdigest()


def artifact_hashes(root, paths):
    return {path: digest((root / path).read_bytes()) for path in paths}


def schedule(graph):
    waiting = {job: len(deps) for job, deps in graph.items()}
    reverse = defaultdict(list)
    for job, deps in graph.items():
        for prerequisite in deps:
            reverse[prerequisite].append(job)
    available = [job for job, outstanding in waiting.items() if outstanding == 0]
    heapify(available)
    order = []
    while available:
        job = heappop(available)
        order.append(job)
        for next_job in reverse[job]:
            waiting[next_job] -= 1
            if waiting[next_job] == 0:
                heappush(available, next_job)
    if len(order) != len(graph):
        raise AssertionError("The admitted build fixture must be acyclic")
    return order


def discover(root, sources):
    dependencies = {}
    lines = command(["gcc", "-MM", *sources], root).decode("ascii").splitlines()
    for line in lines:
        target, colon, prerequisites = line.partition(":")
        if colon != ":" or target in dependencies:
            raise AssertionError(line)
        dependencies[target] = prerequisites.split()
    return dependencies


def materialize(root, expected):
    for path, expected_hash in expected.items():
        payload = (root / "out" / path).read_bytes()
        if digest(payload) != expected_hash:
            raise AssertionError(path)
        (root / "restored" / path).write_bytes(payload)
    return len(expected)


def verify(root, executables):
    return [int(command([root / "out" / name], root)) for name in executables]


def prepare(root, count):
    (root / "out").mkdir(parents=True)
    (root / "restored").mkdir()
    (root / "common.h").write_text("#define OFFSET 42\n")
    sources = []
    dependencies = {}
    outputs = []
    graph = {}
    executables = []
    for index in range(count):
        name = f"part{index:02d}"
        lib, main = f"{name}_lib", f"{name}_main"
        for unit, content, headers in (
            (lib, f'#include "common.h"\nint value(void) {{ return {index} + OFFSET; }}\n',
             ["common.h"]),
            (main, '#include <stdio.h>\nint value(void);\n'
                   'int main(void) { printf("%d\\n", value()); return 0; }\n', []),
        ):
            source, object_ = f"{unit}.c", f"{unit}.o"
            (root / source).write_text(content)
            sources.append(source)
            dependencies[object_] = [source, *headers]
            command(["gcc", *FLAGS, "-c", source, "-o", f"out/{object_}"], root)
            outputs.append(object_)
            graph[f"compile_{unit}"] = []
        library, app = f"{name}.a", f"{name}.exe"
        command(["ar", "rcD", f"out/{library}", f"out/{lib}.o"], root)
        command(["gcc", f"out/{main}.o", f"out/{library}", "-Wl,--build-id=none", "-o", f"out/{app}"], root)
        outputs += [library, app]
        executables.append(app)
        graph[f"archive_{name}"] = [f"compile_{lib}"]
        graph[f"link_{name}"] = [f"compile_{main}", f"archive_{name}"]
        graph[f"verify_{name}"] = [f"link_{name}"]
    key_paths = [*sources, "common.h", *(f"out/{path}" for path in outputs)]
    stored = {path: digest((root / "out" / path).read_bytes()) for path in outputs}
    oracle = {
        "discovery": dependencies, "hashing": artifact_hashes(root, key_paths),
        "verification": list(range(42, 42 + count)), "storage": len(stored),
    }
    return sources, graph, executables, key_paths, stored, oracle


def verify_order(result, graph):
    locations = {label: index for index, label in enumerate(result)}
    return set(locations) == set(graph) and all(locations[dep] < locations[job]
                                              for job, deps in graph.items() for dep in deps)


def measure(root, components, repetitions, randomizer):
    sources, graph, executables, key_paths, stored, oracle = prepare(root, components)
    jobs = {
        "discovery": lambda: discover(root, sources),
        "hashing": lambda: artifact_hashes(root, key_paths),
        "scheduling": lambda: schedule(graph),
        "storage": lambda: materialize(root, stored),
        "verification": lambda: verify(root, executables),
    }
    samples = []

    def time_one(job):
        if job == "storage":
            for path in stored:
                (root / "restored" / path).unlink(missing_ok=True)
        start = perf_counter_ns()
        observed = jobs[job]()
        elapsed = perf_counter_ns() - start
        if job == "scheduling":
            if not verify_order(observed, graph):
                raise AssertionError(observed)
        elif observed != oracle[job]:
            raise AssertionError((job, observed, oracle[job]))
        return elapsed

    for job in PHASES:
        time_one(job)
    for trial in range(repetitions):
        order = list(PHASES)
        randomizer.shuffle(order)
        samples.append({"trial": trial, "order": order, "phase_ns": {job: time_one(job) for job in order}})
    restored = {name: digest((root / "restored" / name).read_bytes()) for name in stored}
    if restored != stored:
        raise AssertionError("The completed storage phase changed output bytes")
    return {
        "components": components, "translation_units": len(sources), "graph_jobs": len(graph),
        "storage_payloads": len(stored), "verification_invocations": len(executables),
        "hash_input_bytes": sum((root / path).stat().st_size for path in key_paths),
        "storage_payload_bytes": sum((root / "out" / path).stat().st_size for path in stored),
        "source_and_output_hashes": oracle["hashing"], "verified_integers": oracle["verification"],
        "samples": samples,
    }


def machine(root):
    cpu = next((line.partition(":")[2].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")), "unknown")
    cgroup_cpu = Path("/sys/fs/cgroup/cpu.max")
    return {
        "python": platform.python_version(), "host": platform.machine(), "kernel": platform.release(),
        "processor": cpu, "affinity": sorted(os.sched_getaffinity(0)),
        "cgroup_cpu_max": cgroup_cpu.read_text().strip() if cgroup_cpu.is_file() else None,
        "temporary_fs_type": command(["stat", "-f", "-c", "%T", root], root).decode().strip(),
        "tools": {
            tool: {"version": command([tool, "--version"], root).decode().splitlines()[0],
                   "sha256": digest(Path(shutil.which(tool)).read_bytes())}
            for tool in ("gcc", "ar")
        },
    }


def run(repetitions, seed):
    randomizer = random.Random(seed)
    with TemporaryDirectory(prefix="llmlang-build-overhead-") as tmp:
        root = Path(tmp)
        return {
            "schema": "llmlang-build-phase-overhead/1", "platform": machine(root),
            "runner_sha256": digest(Path(__file__).read_bytes()), "seed": seed, "trials_per_size": repetitions,
            "workloads": [measure(root / f"w{count}", count, repetitions, randomizer) for count in SIZES],
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=17)
    parser.add_argument("--seed", type=int, default=318)
    args = parser.parse_args()
    if args.trials < 2:
        parser.error("provide at least two trials")
    print(json.dumps(run(args.trials, args.seed), indent=2))
