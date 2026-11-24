"""Exercise native Go with both standalone and C-callable boundary adapters."""

import argparse
from collections import Counter
import ctypes
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
from random import Random
import re
import struct
import subprocess
from tempfile import TemporaryDirectory

from lower_go import cgo_exports, lower, registry
from integer_fixture import OPERATIONS, SOURCE, compile_source, evaluate
from llvm_integer_probe import _BOUNDARIES, _EMIT, _STATUS, _entry


HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parents[1] / "PROTOTYPES" / "LLVM-PRESERVATION-01"
SENTINEL = 0xabad1234
GO_VERSION = "go version go1.27.4 linux/amd64"
GO_SHA256 = "7226736c2339719cda28fbf3a54d71aa63bcefe376e98cef00034268dab24840"


def run(*command, cwd=None, env=None, stdin=None):
    result = subprocess.run(list(map(str, command)), cwd=cwd, env=env, input=stdin,
                            capture_output=True, timeout=180)
    if result.returncode or result.stderr:
        raise ValueError(f"{command!r}\n{result.stderr.decode(errors='replace')}")
    return result.stdout


def source(operation, left="a", right="b"):
    return SOURCE.replace("operation(a, b)", f"{operation}({left}, {right})")


def vectors():
    rng = Random(134)
    pairs = [*product(_BOUNDARIES, repeat=2),
             *((rng.getrandbits(32), rng.getrandbits(32)) for _ in range(256))]
    return tuple((a, b, enable) for (a, b), enable in product(pairs, (0, 1, 2, 0x80000000, 0xffffffff)))


def reference(program, case):
    a, b, enable = case
    observed = evaluate(program, a, b, bool(enable))
    return observed.status, SENTINEL if observed.value is None else observed.value, observed.events


def emit_project(directory, kernels, adapter, count):
    directory.mkdir()
    (directory / "go.mod").write_text("module llmlang.local/loweringgo\n\ngo 1.27\n", encoding="utf-8")
    (directory / "kernels.go").write_text(kernels, encoding="utf-8")
    if adapter == "shared":
        (directory / "exports.go").write_text(cgo_exports(count), encoding="utf-8")
    else:
        (directory / "main.go").write_bytes((HERE / "host.go").read_bytes())
        (directory / "registry.go").write_text(registry(count), encoding="utf-8")


def build(args, directory, adapter):
    flags = {
        "GOCACHE": str(args.cache.resolve()), "CGO_ENABLED": "1" if adapter == "shared" else "0",
        "GOTOOLCHAIN": "local", "GOOS": "linux", "GOARCH": "amd64", "GOAMD64": "v1",
        "GOENV": "off", "GOPROXY": "off", "GOSUMDB": "off", "GOMAXPROCS": "2",
        "CC": args.cc, "GOFLAGS": "", "GOWORK": "off",
    }
    mode = "c-shared" if adapter == "shared" else "exe"
    output = directory / ("probe.so" if adapter == "shared" else "probe")
    run(args.go, "build", "-p", "2", "-mod=readonly", "-buildvcs=false", "-trimpath",
        f"-buildmode={mode}", "-ldflags", "-s -w -buildid=", "-o", output, ".",
        cwd=directory, env={**os.environ, **flags})
    return output


def standalone(executable, indexed_vectors):
    packet = b"".join(struct.pack("<4I", index, *case) for index, case in indexed_vectors)
    response = run(executable, stdin=packet)
    if len(response) != 20 * len(indexed_vectors):
        raise ValueError("Incorrect response record count")
    for status, slot, count, event0, event1 in struct.iter_unpack("<5I", response):
        if count not in (1, 2):
            raise ValueError("Unexpected callback count")
        yield _STATUS[status], slot, (event0, event1)[:count]


def shared(library, indexed_vectors, count):
    loaded = ctypes.CDLL(str(library))
    entries = tuple(_entry(loaded, i) for i in range(count))
    for index, case in indexed_vectors:
        out = ctypes.c_uint32(SENTINEL)
        events = []
        status = entries[index](*case, _EMIT(events.append), ctypes.byref(out))
        yield _STATUS[status], out.value, tuple(events)


def observation_count(observed, expected):
    counts = Counter()
    for seen, wanted in zip(observed, expected, strict=True):
        if seen != wanted:
            raise AssertionError(f"Go observation {seen!r} differs from {wanted!r}")
        counts[seen[0]] += 1
    return {"observations": sum(counts.values()), "statuses": dict(sorted(counts.items()))}


def artifact(args, path):
    dynamic = run(args.readelf, "-d", path).decode()
    return {"bytes": path.stat().st_size, "sha256": sha256(path.read_bytes()).hexdigest(),
            "needed": re.findall(r"Shared library: \[([^\]]+)\]", dynamic)}


def controls(args, work):
    results = {}
    for name, operation, witness, anchors, fields in (
        ("signed_min_divide_by_minus_one", "checked_sdiv", (0x80000000, 0xffffffff, 1),
         (("        if int32(a) == -2147483648 && int32(b) == -1 { return 1 }\n", ""),),
         {"status", "slot", "events"}),
        ("unchecked_oversized_shift", "checked_shl", (7, 32, 1),
         (("        if b >= 32 { return 3 }\n", ""),), {"status", "slot", "events"}),
        ("reverse_callbacks", "wrap_add", (7, 2, 1),
         (("    emit(a)\n", ""), ("    emit(value)\n", "    emit(value)\n    emit(a)\n")), {"events"}),
    ):
        program = compile_source(source(operation))
        emitted = lower((program,))
        for old, replacement in anchors:
            if emitted.count(old) != 1:
                raise ValueError(f"Missing mutation anchor for {name}")
            emitted = emitted.replace(old, replacement)
        directory = work / name
        emit_project(directory, emitted, "host", 1)
        executable = build(args, directory, "host")
        actual, = standalone(executable, [(0, witness)])
        wanted = reference(program, witness)
        changed = {key for key, a, b in zip(("status", "slot", "events"), wanted, actual) if a != b}
        if changed != fields:
            raise AssertionError(f"Unexpected mutation outcomes {name}: {actual}")
        results[name] = {"input": witness, "expected": wanted, "actual": actual, "changed": sorted(changed)}
    return results


def main(args):
    version = run(args.go, "version").decode().strip()
    if version != GO_VERSION:
        raise ValueError(f"Unexpected Go version: {version}")
    programs = tuple(compile_source(source(op, left, right))
                     for op, (left, right) in product(OPERATIONS, product("ab", repeat=2)))
    cases = vectors()
    indexed = [(index, case) for index in range(len(programs)) for case in cases]
    expected = [reference(programs[index], case) for index, case in indexed]
    kernels = lower(programs)
    with TemporaryDirectory(prefix="llmlang-go-integer-") as directory:
        work = Path(directory)
        for adapter in ("host", "shared"):
            emit_project(work / adapter, kernels, adapter, len(programs))
        host, ffi = (build(args, work / adapter, adapter) for adapter in ("host", "shared"))
        header = ffi.with_suffix(".h")
        api = re.findall(r"^extern uint32_t probe_(\d+)\(", header.read_text(), re.MULTILINE)
        if sorted(map(int, api)) != list(range(len(programs))):
            raise ValueError("The Go-generated C header did not expose the expected ABI")
        symbols = run(args.nm, "--dynamic", "--defined-only", ffi).decode()
        exports = re.findall(r"\bT probe_(\d+)$", symbols, re.MULTILINE)
        if sorted(map(int, exports)) != list(range(len(programs))):
            raise ValueError("The Go shared library did not export the expected symbols")
        facts = {
            "standalone": {**artifact(args, host), **observation_count(standalone(host, indexed), expected)},
            "c_shared": {**artifact(args, ffi), **observation_count(shared(ffi, indexed, len(programs)), expected),
                         "checked_c_exports": len(exports)},
        }
        negatives = controls(args, work)
    inputs = (HERE / "run.py", HERE / "lower_go.py", HERE / "host.go",
              FIXTURE / "llvm_integer_probe.py", FIXTURE / "integer_fixture.py")
    return {
        "toolchain": version, "go_archive_sha256": GO_SHA256, "cpu": "GOAMD64=v1",
        "c_compiler": run(args.cc, "--version").decode().splitlines()[0],
        "kernel_source_sha256": sha256(kernels.encode()).hexdigest(),
        "input_sha256": {path.name: sha256(path.read_bytes()).hexdigest() for path in inputs},
        "programs": len(programs), "vectors": len(cases), "profiles": facts, "controls": negatives,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, default in (("go", "go"), ("cc", "gcc"), ("nm", "llvm-nm-19"), ("readelf", "readelf")):
        parser.add_argument(f"--{name}", default=default)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(main(args), sort_keys=True, indent=2) + "\n", encoding="utf-8")
