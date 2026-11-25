"""Compare default, named and interposed Rust and C allocation in fresh processes."""

import argparse
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
ALIGNS = (8, 16, 64, 128, 256, 4096)
SIZES = (1, 7, 31, 128, 1024, 4096)


def run(*args, cwd=None):
    env = {**os.environ, "LC_ALL": "C", "TZ": "UTC", "SOURCE_DATE_EPOCH": "1764000000"}
    env.pop("LD_PRELOAD", None)
    env.pop("MIMALLOC_VERBOSE", None)
    observed = subprocess.run(
        args, cwd=cwd, env=env, capture_output=True, text=True, timeout=90,
    )
    assert observed.returncode == 0, (args[0], observed.stderr)
    return observed.stdout.strip()


def hash_file(path):
    return sha256(path.read_bytes()).hexdigest()


def archive(args, root, mode, source):
    root.mkdir()
    run(args.cmake, "-S", source, "-B", root, "-DCMAKE_BUILD_TYPE=Release",
        "-DMI_BUILD_STATIC=ON", "-DMI_BUILD_SHARED=OFF", "-DMI_BUILD_OBJECT=OFF",
        "-DMI_BUILD_TESTS=OFF", f"-DMI_OVERRIDE={mode}", f"-DCMAKE_C_COMPILER={args.cc}",
        f"-DCMAKE_C_FLAGS=-ffile-prefix-map={source}=/mimalloc")
    run(args.cmake, "--build", root, "--target", "mimalloc-static", "--parallel", "2")
    results = list(root.glob("libmimalloc*.a"))
    assert len(results) == 1
    result = results[0]
    is_interposed = any(row.split()[-2:] == ["T", "malloc"]
                        for row in run("nm", "--defined-only", result).splitlines())
    assert is_interposed == (mode == "ON")
    return result


def oracle(size, salt):
    return sum((index + 1) * ((index * 59 + salt) % 256) for index in range(size))


def build_bridge(args, source, destination):
    run(args.cc, "-std=c17", "-O2", "-fPIC", "-Wall", "-Wextra", "-Werror",
        "-I", source / "include", "-c", HERE / "bridge.c", "-o", destination)


def executable(args, work, bridge, library, program, extra_flags):
    run(args.rustc, "--edition=2021", "-Dwarnings", "-Copt-level=2",
        "--remap-path-prefix", f"{work}=/fixture",
        *extra_flags, "-Clink-arg=" + str(bridge), "-Clink-arg=-Wl,--whole-archive",
        "-Clink-arg=" + str(library), "-Clink-arg=-Wl,--no-whole-archive", "-Clink-arg=-lc",
        "probe.rs", "-o", program, cwd=work)


def legacy_control(args, work):
    source = args.legacy_source
    library = archive(args, work / "legacy", "OFF", source)
    bridge = work / "legacy-bridge.o"
    build_bridge(args, source, bridge)
    program = work / "legacy-control"
    executable(args, work, bridge, library, program, [])
    env = {**os.environ, "LC_ALL": "C"}
    env.pop("LD_PRELOAD", None)
    outcome = subprocess.run([program], capture_output=True, text=True, timeout=10, env=env)
    assert outcome.returncode == 101
    assert "size=1024 alignment=256 salt=11" in outcome.stderr
    assert "public-malloc 0" in outcome.stdout
    return {
        "source_header_sha256": hash_file(source / "include/mimalloc.h"),
        "archive_sha256": hash_file(library), "tested_size": 1024, "requested_alignment": 256,
        "outcome": "component alignment guard refused before access",
    }


def collect(args, work):
    plain = archive(args, work / "plain", "OFF", args.mimalloc_source)
    interposed = archive(args, work / "interposed", "ON", args.mimalloc_source)
    assert hash_file(plain) != hash_file(interposed)
    bridge = work / "bridge.o"
    build_bridge(args, args.mimalloc_source, bridge)
    shutil.copyfile(HERE / "probe.rs", work / "probe.rs")
    rows = {}
    for name, library, flag, owner in (
        ("system_with_named_component", plain, [], (0, 0, 0)),
        ("named_rust_global", plain, ["--cfg", "named_rust"], (0, 1, 0)),
        ("whole_process_override", interposed, [], (1, 1, 1)),
    ):
        program = work / name
        executable(args, work, bridge, library, program, flag)
        symbols = run("nm", "--defined-only", program)
        assert " mi_malloc_aligned" in symbols
        dynamic = run("readelf", "-dW", program)
        libraries = re.findall(r"\(NEEDED\).*\[([^]]+)\]", dynamic)
        assert "libc.so.6" in libraries and not any("mimalloc" in item for item in libraries)
        output = run(program).splitlines()
        assert output[0] == f"public-malloc {owner[0]}"
        observations = [tuple(map(int, line.split())) for line in output[1:]]
        expected = [(size, alignment, owner[1], owner[2],
                     oracle(size, 3), oracle(size, 7), oracle(size, 11), 0)
                    for alignment, size in product(ALIGNS, SIZES)]
        assert observations == expected, name
        rows[name] = {
            "exact_archive_sha256": hash_file(library), "elf_sha256": hash_file(program),
            "dynamic_libraries": libraries, "public_malloc_owned_by_executable": bool(owner[0]),
            "rust_memory_mimalloc_region": bool(owner[1]), "c_memory_mimalloc_region": bool(owner[2]),
            "checked_layouts": len(observations), "wrong_component_releases_refused": len(observations),
            "ordered_output_sha256": sha256("\n".join(output).encode("ascii")).hexdigest(),
        }
    return {
        "providers": {"non_interposed": hash_file(plain), "interposed": hash_file(interposed)},
        "profiles": rows, "legacy_2_0_9": legacy_control(args, work),
        "toolchain": {
            "rustc": run(args.rustc, "--version"), "cc": run(args.cc, "--version").splitlines()[0],
            "cmake": run(args.cmake, "--version").splitlines()[0],
        },
        "sources": {name: hash_file(HERE / name) for name in ("run.py", "probe.rs", "bridge.c")},
        "allocator_source_pins": {
            name: hash_file(args.mimalloc_source / name) for name in
            ("CMakeLists.txt", "include/mimalloc.h", "src/static.c")
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--rustc", default="rustc")
    parser.add_argument("--cmake", default="cmake")
    parser.add_argument("--mimalloc-source", type=Path, required=True)
    parser.add_argument("--legacy-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt25-static-allocator-") as directory:
        evidence = collect(args, Path(directory))
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
