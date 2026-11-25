#!/usr/bin/env python3
"""Measure forced and incremental builds of three pinned upstream libraries."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import random
import shutil
import subprocess
import sys
from tarfile import open as tar_open
from tempfile import TemporaryDirectory
from time import perf_counter_ns

HERE = Path(__file__).resolve().parent
PROJECTS = {
    "memchr": ("8ad339524d857a2dd9e7231b497ed92aa0f5c334",
               "b4e3ce5b8830a5a7ca0c1b41d4962039dd5d4d30491328fe7e5e67020b856c2f"),
    "pflag": ("5ca813443bd2a4d9f46a253ea0407d23b3790713",
              "bedd14093c235a18d05f85ab365ac52b9ea5fb3bdec14e02732cfec0ee3817c4"),
    "fmt": ("123913715afeb8a437e6388b4473fcc4753e1c9a",
            "95f89f1eb3b53478417185afc0b7e3d40ec889687af86e890da20068534d29f7"),
}
STAGES = (("cold", 0), ("warm", 0), ("edited", 1))
METHODS = ("clean", "incremental")
SMOKE = "llmlang_smoke"


def digest(raw):
    return sha256(raw).hexdigest()


def run_command(args, cwd, env):
    result = subprocess.run(args, cwd=cwd, env=env, check=False, capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError((list(map(str, args)), result.returncode,
                            result.stdout.decode(errors="replace")[-4000:],
                            result.stderr.decode(errors="replace")[-4000:]))
    return result.stdout


def append(path, text):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(text)


def extract(archive, destination, name):
    revision, expected = PROJECTS[name]
    if digest(archive.read_bytes()) != expected:
        raise AssertionError(f"Pinned source bytes differ for {archive.name}")
    destination.mkdir()
    with tar_open(archive) as tar:
        tar.extractall(destination, filter="data")
    directory = destination / f"{name}-{revision}"
    if not directory.is_dir():
        raise AssertionError((name, directory))
    return directory


def prepare_probe(name, source):
    if name == "memchr":
        shutil.copyfile(HERE / "memchr-Cargo.lock", source / "Cargo.lock")
        path = source / "src/lib.rs"
        append(path, '''
#[doc(hidden)]
pub fn llmlang_bench_value() -> usize {
    memchr(b'b', b"abc").unwrap() + LLMLANG_BENCH_OFFSET
}
const LLMLANG_BENCH_OFFSET: usize = 0;
''')
        (source / "src/bin").mkdir(exist_ok=True)
        (source / "src/bin/llmlang_smoke.rs").write_text(
            'fn main() { println!("{}", memchr::llmlang_bench_value()); }\n')
        return path, b"usize = 0;", b"usize = 1;", 1
    if name == "pflag":
        path = source / "llmlang_probe.go"
        path.write_text('''package pflag

func LLMLangBenchValue() int {
    fs := NewFlagSet("probe", ContinueOnError)
    fs.Bool("ok", false, "")
    if err := fs.Set("ok", "true"); err != nil {
        panic(err)
    }
    return fs.NFlag() + llmlangBenchOffset
}
const llmlangBenchOffset = 0
''')
        (source / SMOKE).mkdir()
        (source / SMOKE / "main.go").write_text('''package main

import (
    "fmt"
    "github.com/spf13/pflag"
)
func main() { fmt.Println(pflag.LLMLangBenchValue()) }
''')
        return path, b"llmlangBenchOffset = 0", b"llmlangBenchOffset = 1", 1
    path = source / "src/format.cc"
    append(path, '''
int llmlang_bench_value() {
    constexpr int offset = 0;
    return static_cast<int>(fmt::format("{}", 42).size()) + offset;
}
''')
    (source / "llmlang_smoke.cc").write_text('''#include <cstdio>
int llmlang_bench_value();
int main() { std::printf("%d\\n", llmlang_bench_value()); }
''')
    append(source / "CMakeLists.txt", '''
add_executable(llmlang_smoke llmlang_smoke.cc)
target_link_libraries(llmlang_smoke PRIVATE fmt::fmt)
''')
    return path, b"offset = 0;", b"offset = 1;", 2


def prepared_environment(root):
    return {
        **os.environ, "LC_ALL": "C", "SOURCE_DATE_EPOCH": "0",
        "CARGO_BUILD_JOBS": "1", "CARGO_NET_OFFLINE": "true", "CARGO_INCREMENTAL": "1",
        "GOENV": "off", "GOTELEMETRY": "off", "GOTOOLCHAIN": "local", "GOPROXY": "off",
        "GOSUMDB": "off", "CGO_ENABLED": "0", "GOPATH": str(root / "gopath"),
        "GOMODCACHE": str(root / "gomodcache"), "GOFLAGS": "-p=1", "GOMAXPROCS": "1",
    }


def standard_go_cache(args, source, seed, env):
    env = {**env, "GOCACHE": str(seed)}
    listed = run_command([args.go, "list", "-deps", "-buildvcs=false", "-f={{if .Standard}}{{.ImportPath}}{{end}}",
                          f"./{SMOKE}"], source, env)
    standard = sorted({name for line in listed.decode().splitlines() if (name := line.strip())})
    if "fmt" not in standard or "github.com/spf13/pflag" in standard:
        raise AssertionError(standard)
    run_command([args.go, "build", "-trimpath", "-buildvcs=false", *standard], source, env)
    return standard


def recipe(name, source, target, args, base_env, go_seed):
    initialize = not target.exists()
    if name == "memchr":
        env = {**base_env, "CARGO_TARGET_DIR": str(target), "CARGO_HOME": str(args.cargo_home),
               "RUSTFLAGS": f"--remap-path-prefix={source}=/source/memchr"}
        command = [args.cargo, "build", "--release", "--offline", "--locked", "--bin", SMOKE]
        return command, target / "release" / SMOKE, env
    if name == "pflag":
        if initialize:
            shutil.copytree(go_seed, target)
        binary = target / SMOKE
        env = {**base_env, "GOCACHE": str(target)}
        command = [args.go, "build", "-trimpath", "-buildvcs=false", "-o", binary, f"./{SMOKE}"]
        return command, binary, env
    if initialize:
        run_command([
            args.cmake, "-S", source, "-B", target, "-G", "Unix Makefiles", "-DCMAKE_BUILD_TYPE=Release",
            f"-DCMAKE_CXX_COMPILER={shutil.which('g++')}", "-DFMT_TEST=OFF", "-DFMT_DOC=OFF",
            "-DFMT_INSTALL=OFF", "-DBUILD_SHARED_LIBS=OFF", "-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY=ON",
            "-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF",
        ], source, base_env)
    command = [args.cmake, "--build", target, "--target", SMOKE, "--parallel", "1"]
    return command, target / "bin" / SMOKE, base_env


def measure_trial(name, source, trial_dir, args, env, go_seed, order_rng):
    edit_path, old, changed, expected_base = prepare_probe(name, source)
    unchanged_content = edit_path.read_bytes()
    if unchanged_content.count(old) != 1:
        raise AssertionError(f"Ambiguous probe edit in {edit_path.name}")
    results = []
    for stage, edit in STAGES:
        if edit:
            edit_path.write_bytes(unchanged_content.replace(old, changed))
        methods = list(METHODS)
        order_rng.shuffle(methods)
        samples = {}
        for method in methods:
            target = trial_dir / (f"clean-{stage}" if method == "clean" else "incremental")
            command, binary, current_env = recipe(name, source, target, args, env, go_seed)
            start = perf_counter_ns()
            run_command(command, source, current_env)
            elapsed_ns = perf_counter_ns() - start
            observed = int(run_command([binary], source, current_env))
            if observed != expected_base + edit:
                raise AssertionError((name, stage, method, observed, expected_base + edit))
            samples[method] = {"elapsed_ns": elapsed_ns, "value": observed,
                               "binary_sha256": digest(binary.read_bytes()), "binary_bytes": binary.stat().st_size}
        results.append({"stage": stage, "method_order": methods, "measurements": samples,
                        "binary_bytes_agree": samples["clean"]["binary_sha256"] == samples["incremental"]["binary_sha256"]})
    return {"modified_source": edit_path.relative_to(source).as_posix(),
            "source_sha256_before_edit": digest(unchanged_content),
            "source_sha256_after_edit": digest(edit_path.read_bytes()), "stages": results}


def machine(root, args, env):
    tool_args = {"cargo": [args.cargo, "--version"], "rustc": ["rustc", "--version"],
                 "go": [args.go, "version"], "cmake": [args.cmake, "--version"],
                 "g++": ["g++", "--version"], "make": ["make", "--version"]}
    toolchain = {}
    for name, command in tool_args.items():
        executable = Path(shutil.which(command[0])).resolve()
        toolchain[name] = {"version": run_command(command, root, env).decode().splitlines()[0],
                           "sha256": digest(executable.read_bytes())}
    quota = Path("/sys/fs/cgroup/cpu.max")
    return {
        "toolchain": toolchain, "python": platform.python_version(), "kernel": platform.release(),
        "arch": platform.machine(), "affinity": sorted(os.sched_getaffinity(0)),
        "cgroup_cpu_max": quota.read_text().strip() if quota.is_file() else None,
        "filesystem": run_command(["stat", "-f", "-c", "%T", root], root, env).decode().strip(),
    }


def measure(args):
    rng = random.Random(args.seed)
    with TemporaryDirectory(prefix="llmlang-upstream-builds-") as temporary:
        root = Path(temporary)
        env = prepared_environment(root)
        archives = {name: args.sources / f"{name}.tar.gz" for name in PROJECTS}
        go_source = extract(archives["pflag"], root / "go-prepare", "pflag")
        prepare_probe("pflag", go_source)
        go_seed = root / "go-seed"
        standard = standard_go_cache(args, go_source, go_seed, env)
        results = {}
        for name, (revision, archive_hash) in PROJECTS.items():
            selected = []
            for trial in range(args.trials):
                trial_dir = root / f"{name}-{trial}"
                source = extract(archives[name], trial_dir, name)
                selected.append(measure_trial(name, source, trial_dir, args, env, go_seed, rng))
            results[name] = {"revision": revision, "archive_sha256": archive_hash, "trials": selected}
            print(f"Checked {name} across {args.trials} trial blocks", file=sys.stderr, flush=True)
        return {
            "schema": "llmlang-upstream-build-baselines/1", "seed": args.seed, "trials": args.trials,
            "toolchain_and_host": machine(root, args, env),
            "sources_sha256": {name: digest((HERE / name).read_bytes()) for name in ("run.py", "memchr-Cargo.lock")},
            "go_precompiled_standard_packages": standard, "projects": results,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("sources", "cargo-home", "cargo", "go", "cmake"):
        parser.add_argument(f"--{argument}", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=318)
    parser.add_argument("--trials", type=int, default=3)
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("provide at least one trial")
    print(json.dumps(measure(args), indent=2))
