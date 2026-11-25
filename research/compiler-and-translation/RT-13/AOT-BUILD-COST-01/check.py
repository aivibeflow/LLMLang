"""Measure a native LLVM clean/incremental AOT build and checked execution."""

import argparse
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import platform
import random
import shlex
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter_ns


SEED = 20261125
BATCHES = 30
COUNT = 4096
MASK = (1 << 32) - 1
FAMILIES = {"scalar": 4, "dispatch": 8, "table": 16}
MODES = {"debug": ("-O0", "-g"), "release": ("-O3", "-g0")}


def provider(family, index, revision):
    salt = 11 + index * 17 + revision
    fragments = {
        "scalar": "return (x * 1664525u + S) ^ (x >> 9);",
        "dispatch": "switch (x & 3) {case 0: return x + S; case 1: return x ^ (S << 11);"
                    "case 2: return x * (S | 1u); default: return (x >> 2) + (S << 17);}",
        "table": "const uint32_t words[8] = {S, S+3, S+7, S+15, S+31, S+63, S+127, S+255};"
                 "return x ^ words[(x >> 5) & 7];",
    }
    return f"#include <stdint.h>\n#define S {salt}u\nuint32_t op{index}(uint32_t x) {{ {fragments[family]} }}\n"


def oracle(family, modules, revision):
    total = 2166136261
    for index in range(COUNT):
        value = (index * 2654435761) & MASK
        for slot in range(modules):
            salt = 11 + slot * 17 + (revision if slot == 0 else 0)
            if family == "scalar":
                value = (value * 1664525 + salt) ^ (value >> 9)
            elif family == "dispatch":
                choice = value % 4
                value = [value + salt, value ^ (salt * 2048), value * (salt | 1),
                         value // 4 + salt * 131072][choice]
            else:
                word = 0 if value // 32 % 8 == 0 else (1 << (value // 32 % 8 + 1)) - 1
                value ^= salt + word
            value &= MASK
        total = ((total ^ value) * 16777619) & MASK
    return total


def consumer(modules):
    declarations = [f"uint32_t op{x}(uint32_t);" for x in range(modules)]
    calls = [f"        value = op{x}(value);" for x in range(modules)]
    return "\n".join([
        "#define _POSIX_C_SOURCE 200809L",
        "#include <stdint.h>",
        "#include <stdio.h>",
        "#include <time.h>",
        *declarations,
        "int main(void) {",
        "    struct timespec begin, end;",
        "    uint32_t checksum = 2166136261u;",
        "    if (clock_gettime(CLOCK_MONOTONIC, &begin)) return 1;",
        f"    for (uint32_t i = 0; i < {COUNT}u; ++i) {{",
        "        uint32_t value = i * 2654435761u;",
        *calls,
        "        checksum = (checksum ^ value) * 16777619u;",
        "    }",
        "    if (clock_gettime(CLOCK_MONOTONIC, &end)) return 1;",
        "    long long elapsed = (end.tv_sec-begin.tv_sec)*1000000000LL + end.tv_nsec-begin.tv_nsec;",
        '    printf("%u %lld\\n", checksum, elapsed);',
        "    return 0;",
        "}",
        "",
    ])


def timed_process(args, work):
    """Collect one command's Linux child high-water RSS using wait4."""
    sink = work / "command.log"
    start = perf_counter_ns()
    pid = os.fork()
    if pid == 0:
        try:
            with sink.open("wb") as output:
                os.dup2(output.fileno(), 1)
                os.dup2(output.fileno(), 2)
            os.execv(args[0], args)
        finally:
            os._exit(127)
    _, exit_status, usage = os.wait4(pid, 0)
    elapsed = perf_counter_ns() - start
    if not os.WIFEXITED(exit_status) or os.WEXITSTATUS(exit_status):
        raise RuntimeError((shlex.join(args), sink.read_text(errors="replace")))
    return elapsed, usage.ru_maxrss


def run_binary(binary, expected):
    outputs = []
    for _ in range(3):
        checksum, interval = map(int, subprocess.check_output([binary], text=True, timeout=10).split())
        assert checksum == expected and interval > 0
        outputs.append(interval)
    return outputs


def run_trial(clang, linker, work, batch, family, mode, expected):
    modules = FAMILIES[family]
    units = [work / f"op{i}.c" for i in range(modules)] + [work / "caller.c"]
    for index, path in enumerate(units[:-1]):
        path.write_text(provider(family, index, 0))
    units[-1].write_text(consumer(modules))
    objects = [path.with_suffix(".o") for path in units]
    cmd = [clang, *MODES[mode], f"-ffile-prefix-map={work}=.", "-fno-color-diagnostics"]
    stages = {}

    def compile_unit(index):
        return timed_process([*cmd, "-c", str(units[index]), "-o", str(objects[index])], work)

    binary = work / "demo"
    link = [clang, f"--ld-path={linker}", "-Wl,--build-id=none", *(str(path) for path in objects), "-o", str(binary)]
    build = [compile_unit(i) for i in range(len(units))]
    stages["clean_compile_ns"] = sum(time for time, _ in build)
    stages["clean_link_ns"], clean_link_rss = timed_process(link, work)
    stages["clean_peak_tool_kib"] = max(clean_link_rss, *(peak for _, peak in build))
    before = run_binary(binary, expected[0])
    retained = {obj: sha256(obj.read_bytes()).hexdigest() for obj in objects[1:]}
    units[0].write_text(provider(family, 0, 3))
    stages["incremental_compile_ns"], changed_peak = compile_unit(0)
    stages["incremental_link_ns"], link_peak = timed_process(link, work)
    stages["incremental_peak_tool_kib"] = max(changed_peak, link_peak)
    assert all(sha256(obj.read_bytes()).hexdigest() == digest for obj, digest in retained.items())
    after = run_binary(binary, expected[1])
    details = subprocess.check_output(["readelf", "-SW", binary], text=True, timeout=10)
    assert (".debug_line" in details) == (mode == "debug")
    return {"family": family, "mode": mode, "batch": batch, "modules": modules,
            "clean_objects": len(units), "incremental_objects": 1, "checksum": list(expected),
            "provider_calls_per_runtime": COUNT * modules, "binary_bytes": binary.stat().st_size,
            "runtime_batch_ns": {"clean": before, "edited": after}, "stages": stages}


def main(options):
    clang, linker = (os.path.abspath(binary) for binary in (options.clang, options.linker))
    affinity = sorted(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {affinity[0]})
    randomizer = random.Random(SEED)
    expected = {name: tuple(oracle(name, count, revision) for revision in (0, 3))
                for name, count in FAMILIES.items()}
    assert all(prior != current for prior, current in expected.values())
    results = []
    for batch in range(options.batches):
        cases = list(product(FAMILIES, MODES))
        randomizer.shuffle(cases)
        for family, mode in cases:
            with TemporaryDirectory(prefix="llmlang-aot-") as temporary:
                results.append(run_trial(clang, linker, Path(temporary), batch, family, mode, expected[family]))
    with TemporaryDirectory(prefix="llmlang-aot-diagnostic-") as temporary:
        source = Path(temporary) / "invalid.c"
        source.write_text("unsigned selected(unsigned x) { return missing_provider(x); }\n")
        diagnostics = {}
        for mode, flags in MODES.items():
            process = subprocess.run([clang, *flags, "-std=c17", "-fsyntax-only", str(source)],
                                     text=True, capture_output=True, timeout=10, check=False)
            assert process.returncode and "invalid.c:1:40" in process.stderr
            assert "missing_provider" in process.stderr
            diagnostics[mode] = {"error_location": "invalid.c:1:40", "unresolved": "missing_provider"}
    cpu = next(line.partition(":")[2].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
               if line.startswith("model name"))
    return {
        "platform": platform.platform(), "cpu": cpu, "affinity": [affinity[0]], "seed": SEED,
        "python": platform.python_version(), "clang": subprocess.check_output([clang, "--version"], text=True).splitlines()[0],
        "linker": subprocess.check_output([linker, "--version"], text=True).splitlines()[0],
        "filesystem": subprocess.check_output(["stat", "-f", "-c", "%T", "/tmp"], text=True).strip(),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "diagnostics": diagnostics, "samples": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", required=True)
    parser.add_argument("--linker", required=True)
    parser.add_argument("--batches", type=int, default=BATCHES)
    arguments = parser.parse_args()
    if arguments.batches <= 0:
        parser.error("batches must be positive")
    print(json.dumps(main(arguments), indent=2, sort_keys=True))
