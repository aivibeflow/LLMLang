"""Compare constrained signed-zero cancellation through native, full and ThinLTO links."""
import argparse
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
TARGET = "x86_64-unknown-linux-gnu"
TOOL_VERSIONS = (
    ("19", "Debian clang version 19.1.7 (3+b1)", "19.1.7"),
    ("22", "clang version 22.1.4 (https://github.com/llvm/llvm-project 35990504507d79e0b9deb809c8ee5e1b34ceef20)", "22.1.4"),
    ("23", "clang version 23.1.1 (https://github.com/llvm/llvm-project 6dfe1677ab8dffbc6ec13d53a1e0215d75147689)", "23.1.1"),
)
LINKS = ("native", "full", "thin")
ROUTES = ("inline_literals", "keep_call", "inline_loads")
MODES = ("nearest", "upward", "downward", "toward-zero")


def command(args, directory):
    return subprocess.run(args, cwd=directory, text=True, capture_output=True, check=True, timeout=45).stdout


def profile(directory, compiler, linker, common_compiler, link_mode, label):
    directory.mkdir()
    common_options = ["-target", TARGET, "-O3"]
    flags = [] if link_mode == "native" else [f"-flto={link_mode}"]
    command([common_compiler, *common_options, "-std=c17", "-Wall", "-Wextra", "-Werror",
             "-c", str(HERE / "host.c"), "-o", "host.o"], directory)
    for module in ("operation", "wrappers"):
        command([compiler, *common_options, *flags, "-c", str(HERE / f"{module}.ll"),
                 "-o", f"{module}.o"], directory)
    command([compiler, *common_options, *flags, f"--ld-path={linker}", "-Wl,--threads=1",
             "operation.o", "wrappers.o", "host.o", "-lm", "-o", "probe"], directory)
    result = command(["./probe"], directory)
    expected = product(enumerate(MODES), (0, 1), ROUTES)
    rows = {}
    for ((index, mode), seed, route), raw in zip(expected, result.splitlines(), strict=True):
        observed_mode, observed_seed, observed_route, bits, flags_equal = raw.split()
        assert (observed_mode, observed_seed, observed_route) == (str(index), str(seed), route)
        assert flags_equal == "1"
        if mode != "downward":
            assert bits == "0000000000000000"
        rows[f"{mode}/{seed}/{route}"] = bits
    disassembly = command(["objdump", "-d", "probe"], directory)
    instructions = {}
    for route in ROUTES:
        match = re.search(rf"(?m)^[0-9a-f]+ <{route}>:\n(.*?)(?:\n\n|\Z)", disassembly, re.S)
        if not match:
            raise ValueError((label, route))
        instructions[route] = {
            "calls_or_jumps_to_dynamic_sum": bool(re.search(r"\b(?:callq?|jmpq?).*<dynamic_sum>", match[1])),
            "retained_addsd": bool(re.search(r"\bv?addsd\b", match[1])),
        }
    return {
        "results": rows, "evidence_sha256": sha256(result.encode()).hexdigest(),
        "assembly_observations": instructions,
    }


def run(directory, tool_roots):
    versions = {}
    rows = {}
    common_compiler = tool_roots[0] / "clang"
    for (key, compiler_version, linker_number), root in zip(TOOL_VERSIONS, tool_roots, strict=True):
        compiler, linker = root / "clang", root / "ld.lld"
        observed = command([compiler, "--version"], directory).splitlines()[0]
        linker_version = command([linker, "--version"], directory).strip()
        assert observed == compiler_version and linker_number in linker_version
        versions[key] = {"clang": observed, "linker": linker_version}
        for mode in LINKS:
            name = f"{key}/{mode}"
            summary = profile(directory / name.replace("/", "-"), compiler, linker, common_compiler, mode, name)
            for route in ROUTES:
                expect_negative = mode == "native" or route != "inline_literals"
                expected_bits = "8000000000000000" if expect_negative else "0000000000000000"
                assert all(summary["results"][f"downward/{seed}/{route}"] == expected_bits for seed in (0, 1))
                operations = summary["assembly_observations"][route]
                assert operations["calls_or_jumps_to_dynamic_sum"] == (mode == "native" or route == "keep_call")
                assert operations["retained_addsd"] == (mode != "native" and route == "inline_loads")
            rows[name] = summary
    return {
        "format": "rt13-llvm-rounding-lto/1", "python": sys.version.split()[0],
        "target": TARGET, "toolchains": versions, "rows_per_link": len(MODES) * 2 * len(ROUTES),
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("operation.ll", "wrappers.ll", "host.c")},
        "profiles": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for major in ("19", "22", "23"):
        parser.add_argument(f"--llvm{major}-bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    roots = tuple(getattr(args, f"llvm{major}_bin").resolve() for major in ("19", "22", "23"))
    with TemporaryDirectory(prefix="llmlang-llvm-rounding-lto-") as scratch:
        result = run(Path(scratch), roots)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
