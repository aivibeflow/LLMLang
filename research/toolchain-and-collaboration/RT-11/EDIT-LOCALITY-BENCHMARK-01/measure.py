#!/usr/bin/env python3
"""Measure paired rebuilds after verified edits at three graph scopes."""

import argparse
import csv
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import tempfile
import time

HERE = Path(__file__).resolve().parent
UNITS = 16
GROUP_SIZE = 4
FLAGS = ("-std=c11", "-O2", "-Wall", "-Wextra", "-Werror")
SCENARIOS = {
    "local": ("unit00.c", '#include "common.h"\n#include "group0.h"\n'
                         "int unit00(void) { return COMMON + GROUP + 10; }\n", 10, 1),
    "shared": ("group0.h", "#define GROUP 11\n", 44, 4),
    "broad": ("common.h", "#define COMMON 21\n", 320, 16),
}
ROUTES = ("full", "incremental")


def hash_file(file):
    return sha256(file.read_bytes()).hexdigest()


def call(directory, *args):
    return subprocess.check_output(args, cwd=directory, text=True)


def prepare(directory):
    directory.mkdir()
    (directory / "common.h").write_text("#define COMMON 1\n")
    for group in range(UNITS // GROUP_SIZE):
        (directory / f"group{group}.h").write_text(f"#define GROUP {group}\n")
    names = [f"unit{i:02}" for i in range(UNITS)]
    for number, name in enumerate(names):
        source = f'#include "common.h"\n#include "group{number // GROUP_SIZE}.h"\n'
        source += f"int {name}(void) {{ return COMMON + GROUP + {number}; }}\n"
        (directory / f"{name}.c").write_text(source)
    declarations = "".join(f"int {name}(void);\n" for name in names)
    additions = " + ".join(f"{name}()" for name in names)
    (directory / "main.c").write_text("#include <stdio.h>\n" + declarations +
                                      f'int main(void) {{ return printf("%d\\n", {additions}) < 0; }}\n')
    inputs = {name: (f"{name}.c", "common.h", f"group{i // GROUP_SIZE}.h")
              for i, name in enumerate(names)}
    return {**inputs, "main": ("main.c",)}


def key(directory, files, checked_toolchain):
    inputs = [(name, hash_file(directory / name)) for name in files]
    return sha256(json.dumps([checked_toolchain, FLAGS, inputs], separators=(",", ":")).encode()).hexdigest()


def compile_unit(directory, compiler, name):
    call(directory, compiler, *FLAGS, "-c", f"{name}.c", "-o", f"{name}.o")


def children_cpu_ns():
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    return round((children.ru_utime + children.ru_stime) * 1_000_000_000)


def run(directory, compiler, version, inputs, cache, scenario, route, block):
    file, content, increase, expected_invalidated = SCENARIOS[scenario]
    (directory / file).write_text(content)
    changed = 0
    cpu_start = children_cpu_ns()
    start = time.perf_counter_ns()
    for name, files in inputs.items():
        if route == "incremental":
            cached_key, expected_object = cache[name]
            if key(directory, files, version) == cached_key and hash_file(directory / f"{name}.o") == expected_object:
                continue
        compile_unit(directory, compiler, name)
        changed += 1
    call(directory, compiler, *(f"{name}.o" for name in inputs), "-o", "app")
    elapsed = time.perf_counter_ns() - start
    child_cpu = children_cpu_ns() - cpu_start
    exact_selection = len(inputs) if route == "full" else expected_invalidated
    if changed != exact_selection:
        raise AssertionError((scenario, route, changed, exact_selection))
    expected = sum(1 + i // GROUP_SIZE + i for i in range(UNITS)) + increase
    observed = int(call(directory, str(directory / "app")).strip())
    if observed != expected:
        raise AssertionError((scenario, route, observed, expected))
    return {"scenario": scenario, "block": block, "route": route, "compiles": changed,
            "links": 1, "wall_ns": elapsed, "child_cpu_ns": child_cpu,
            "observed": observed, "artifact_sha256": hash_file(directory / "app")}


def measure(compiler, count):
    rows = []
    with tempfile.TemporaryDirectory() as build:
        work = Path(build)
        source = work / "baseline"
        inputs = prepare(source)
        version = call(source, compiler, "--version").splitlines()[0]
        for name in inputs:
            compile_unit(source, compiler, name)
        cache = {name: (key(source, files, version), hash_file(source / f"{name}.o"))
                 for name, files in inputs.items()}
        for block in range(count):
            for stage, scenario in enumerate(SCENARIOS):
                routes = ROUTES if (block + stage) % 2 == 0 else tuple(reversed(ROUTES))
                checked = []
                for route in routes:
                    project = work / "project"
                    shutil.copytree(source, project)
                    row = run(project, compiler, version, inputs, cache, scenario, route, block)
                    rows.append(row)
                    checked.append(row["artifact_sha256"])
                    shutil.rmtree(project)
                if len(set(checked)) != 1:
                    raise AssertionError(f"Binary mismatch for {scenario}, {block}")
    quota = Path("/sys/fs/cgroup/cpu.max")
    return rows, {"compiler": version, "flags": FLAGS, "blocks": count,
                  "python": platform.python_version(), "platform": platform.platform(),
                  "cpu_affinity": sorted(os.sched_getaffinity(0)),
                  "cgroup_cpu_max": quota.read_text().strip() if quota.is_file() else None,
                  "measured_script_sha256": hash_file(Path(__file__)),
                  "baseline_units": len(inputs)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blocks", default=7, type=int)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.blocks < 1:
        parser.error("--blocks must be positive")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows, profile = measure(os.environ.get("CC", "gcc"), args.blocks)
    with (args.out_dir / "samples.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (args.out_dir / "profile.json").write_text(json.dumps(profile, indent=2) + "\n")


if __name__ == "__main__":
    main()
