"""Compare native code and debug evidence for source formatting revisions."""

import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
from tempfile import TemporaryDirectory

INPUTS = (0, 1, 6, 7, 127, 255, 65535, 1 << 31, (1 << 32) - 2, (1 << 32) - 1)
STYLES = {
    "baseline": "#include <stdint.h>\nuint32_t compute(uint32_t x) {\n    return x + UINT32_C(7);\n}\n",
    "column_edit": "#include <stdint.h>\nuint32_t compute(uint32_t x) {\n\treturn   x + UINT32_C(7);\n}\n",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(directory, *command):
    return subprocess.check_output(command, cwd=directory, text=True,
                                   env=os.environ | {"LC_ALL": "C"})


def compile_profile(directory, text, debug):
    source = directory / "unit.c"
    source.write_text(text, encoding="ascii")
    run(directory, "gcc", "-O2", "-fPIC", "-g" if debug else "-g0",
        "-frandom-seed=llmlang-metadata", f"-fdebug-prefix-map={directory}=/fixture",
        "-c", "unit.c", "-o", "unit.o")
    run(directory, "objcopy", "--dump-section", ".text=code.bin", "unit.o", "copied.o")
    if debug:
        run(directory, "objcopy", "--dump-section", ".debug_line=line.bin", "unit.o", "line-copy.o")
    run(directory, "gcc", "-shared", "unit.o", "-o", "unit.so")
    native = ctypes.CDLL(str(directory / "unit.so")).compute
    native.argtypes = (ctypes.c_uint32,)
    native.restype = ctypes.c_uint32
    rows = run(directory, "readelf", "--debug-dump=decodedline", "unit.o")
    line_rows = re.findall(r"(?m)^unit\.c\s+(\d+)\s+(0x[0-9a-f]+|0)\b", rows)
    raw_rows = run(directory, "readelf", "--debug-dump=rawline", "unit.o")
    return {
        "raw_column_updates": [int(value) for value in re.findall(r"Set column to (\d+)", raw_rows)],
        "object_sha256": sha((directory / "unit.o").read_bytes()),
        "text_sha256": sha((directory / "code.bin").read_bytes()),
        "debug_line_sha256": sha((directory / "line.bin").read_bytes()) if debug else None,
        "decoded_line_rows": [{"line": int(line), "address": address} for line, address in line_rows],
        "observations": [native(value) for value in INPUTS],
    }


def main():
    assert platform.machine() == "x86_64"
    results = {}
    with TemporaryDirectory(prefix="llmlang-column-") as scratch:
        root = Path(scratch)
        versions = {tool: run(root, tool, "--version").splitlines()[0]
                    for tool in ("gcc", "objcopy", "readelf")}
        assert "14.2.0" in versions["gcc"]
        assert all("2.44" in versions[tool] for tool in ("objcopy", "readelf"))
        expected = [(n + 7) % (1 << 32) for n in INPUTS]
        for style, source in STYLES.items():
            builds = {}
            for debug in (False, True):
                label = "debug" if debug else "no_debug"
                directory = root / style / label
                directory.mkdir(parents=True)
                builds[label] = compile_profile(directory, source, debug)
                assert builds[label]["observations"] == expected
                assert bool(builds[label]["decoded_line_rows"]) == debug
                assert bool(builds[label]["raw_column_updates"]) == debug
            assert builds["debug"]["text_sha256"] == builds["no_debug"]["text_sha256"]
            results[style] = {"source": source, "source_sha256": sha(source.encode()), **builds}

    base, edited = results["baseline"], results["column_edit"]
    assert base["source_sha256"] != edited["source_sha256"]
    assert base["no_debug"]["object_sha256"] == edited["no_debug"]["object_sha256"]
    base_debug, changed_debug = base["debug"], edited["debug"]
    assert base_debug["text_sha256"] == changed_debug["text_sha256"]
    assert base_debug["object_sha256"] != changed_debug["object_sha256"]
    assert base_debug["decoded_line_rows"] == changed_debug["decoded_line_rows"]
    assert base_debug["debug_line_sha256"] != changed_debug["debug_line_sha256"]
    assert base_debug["raw_column_updates"] != changed_debug["raw_column_updates"]
    return {
        "schema": "llmlang-rt11-debug-column-reuse/1", "python": platform.python_version(),
        "architecture": platform.machine(), "tools": versions, "runner_sha256": sha(Path(__file__).read_bytes()),
        "inputs": INPUTS, "profiles": results,
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
