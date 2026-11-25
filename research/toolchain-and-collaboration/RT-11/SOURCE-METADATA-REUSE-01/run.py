#!/usr/bin/env python3
"""Compare source metadata, exact native artifacts and observed behavior."""

from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import shutil
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ENV = {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}
MASK = (1 << 32) - 1
INPUTS = (0, 1, 2, 3, 7, 10, 33, 128, 255, 256, 512, 1 << 20, 1 << 31, MASK - 1, MASK)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def call(args, directory, *, source=None):
    return subprocess.run(args, cwd=directory, input=source, env=ENV, text=True, capture_output=True,
                          timeout=30, check=True).stdout


def variants(source):
    return {
        "baseline": source,
        "same-line-comment": source.replace("Source-location profile fixture.", "A distinct comment."),
        "leading-lines": "\n\n" + source,
        "trailing-comment": source + "\n/* Additional trailing note. */\n",
    }


def build(directory, source, debug, use_line):
    input_file = directory / "input.c"
    input_file.write_text(source, encoding="ascii")
    compile_args = [
        "gcc", "-O2", "-std=c17", "-Wall", "-Wextra", "-Werror", "-fno-ident",
        f"-DUSE_LINE={int(use_line)}", "-g" if debug else "-g0",
        f"-fdebug-prefix-map={directory}=/fixture", "-c", "input.c", "-o", "input.o",
    ]
    link_args = ["gcc", "-O2", "-std=c17", "-Wall", "-Wextra", "-Werror", "driver.c", "input.o", "-o", "app"]
    call(compile_args, directory)
    call(link_args, directory)
    call(["objcopy", "--only-section=.text", "-O", "binary", "input.o", "text.bin"], directory)
    nm_rows = [line.split() for line in call(["nm", "--defined-only", "app"], directory).splitlines()]
    address, = [row[0] for row in nm_rows if row[-1] == "step"]
    location = call(["addr2line", "-e", "app", address], directory).strip()
    observed = [int(line) for line in call(["./app"], directory, source="".join(f"{x}\n" for x in INPUTS)).splitlines()]
    line = next(i for i, text in enumerate(source.splitlines(), 1) if "__LINE__" in text)
    expected = [(value + (line if use_line else 1)) & MASK for value in INPUTS]
    if observed != expected:
        raise AssertionError("Native vector disagrees with the exact location or constant oracle")
    if debug and not location.startswith("/fixture/input.c:"):
        raise AssertionError(f"Missing mapped statement location: {location}")
    if not debug and location != "??:?":
        raise AssertionError(f"Unexpected line location without DWARF: {location}")
    return {
        "source_sha256": digest(input_file), "object_sha256": digest(directory / "input.o"),
        "text_sha256": digest(directory / "text.bin"), "machine_location": location,
        "line_macro_value": line if use_line else None, "observations": observed,
        "compile": [arg.replace(str(directory), "<scratch>") for arg in compile_args], "link": link_args,
    }


def results():
    source = (HERE / "input.c").read_text(encoding="ascii")
    rows = {}
    with TemporaryDirectory(prefix="llmlang-source-metadata-") as temp:
        directory = Path(temp)
        shutil.copyfile(HERE / "driver.c", directory / "driver.c")
        tools = {}
        for tool in ("gcc", "ld", "objcopy", "nm", "addr2line"):
            path = Path(shutil.which(tool, path=ENV["PATH"]))
            tools[tool] = {"banner": call([str(path), "--version"], directory).splitlines()[0],
                           "sha256": digest(path)}
        for use_line, debug in product((False, True), repeat=2):
            profile = ("line" if use_line else "pure") + ("-debug" if debug else "-plain")
            rows[profile] = {name: build(directory, text, debug, use_line) for name, text in variants(source).items()}
    compared = {}
    fields = ("source_sha256", "object_sha256", "text_sha256", "machine_location", "observations")
    for profile, cases in rows.items():
        baseline = cases["baseline"]
        compared[profile] = {
            name: {field: baseline[field] == case[field] for field in fields}
            for name, case in cases.items() if name != "baseline"
        }
    return {
        "schema": "llmlang-source-metadata-reuse/1",
        "host": {"python": platform.python_version(), "kernel": platform.release(), "arch": platform.machine()},
        "tools": tools, "environment": ENV, "inputs": INPUTS,
        "sources_sha256": {name: digest(HERE / name) for name in ("input.c", "driver.c", "run.py")},
        "profiles": rows, "comparison_to_baseline": compared,
    }


if __name__ == "__main__":
    print(json.dumps(results(), indent=2))
