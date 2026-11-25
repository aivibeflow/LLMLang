"""Check one shared C receiver runtime via four independently linked host adapters."""

import argparse
from collections import Counter
import ctypes
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
ADAPTER = {"c": "adapter.c", "cpp": "adapter.cc", "go": "adapter.go", "rust": "adapter.rs"}
MAX_U32 = 2**32 - 1
STATES = (0, 1, 17, 254, 255, 256, MAX_U32)
CHANGES = (-(2**31), -256, -255, -1, 0, 1, 17, 255, 256, 2**31 - 1)
GRANTS = (0, 1, 2, 3, 4, MAX_U32)


def execute(command, directory, *, check=True, flags=None):
    env = {**os.environ, "LC_ALL": "C", **(flags or {})}
    return subprocess.run(command, cwd=directory, env=env, check=check, capture_output=True,
                          text=True, timeout=90)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def build_archive(args, work):
    obj = work / "receiver.o"
    archive = work / "libreceiver.a"
    execute([args.cc, "-std=c17", "-O2", "-fPIC", "-Wall", "-Wextra", "-Werror",
             "-c", str(HERE / "runtime.c"), "-o", str(obj)], work)
    execute([args.ar, "rcsD", str(archive), str(obj)], work)
    return archive


def build_adapter(args, directory, profile, archive):
    directory.mkdir()
    shutil.copyfile(HERE / "runtime.h", directory / "runtime.h")
    if archive:
        shutil.copyfile(archive, directory / archive.name)
    code = directory / ADAPTER[profile]
    text = (HERE / f"{ADAPTER[profile]}.in").read_text(encoding="utf-8")
    if profile == "go" and not archive:
        text = "// Separate missing-runtime link control.\n" + text
    code.write_text(text, encoding="utf-8")
    target = directory / "probe.so"
    environment = None
    if profile in ("c", "cpp"):
        compiler, language = (args.cc, "c17") if profile == "c" else (args.cxx, "c++20")
        command = [compiler, f"-std={language}", "-O2", "-fPIC", "-Wall", "-Wextra", "-Werror",
                   "-shared", "-Wl,--no-undefined", str(code), "-L.", "-lreceiver", "-o", str(target)]
    elif profile == "rust":
        command = [args.rustc, "--edition=2021", "--crate-name=receiverprobe", "--crate-type=cdylib",
                   "-Copt-level=2", "-Cdebuginfo=0", "--remap-path-prefix", f"{directory}=/fixture",
                   "-L", "native=.", str(code), "-o", str(target)]
    else:
        (directory / "go.mod").write_text("module llmlang.local/receiverprobe\n\ngo 1.27\n", encoding="utf-8")
        environment = {
            "GOCACHE": str(args.go_cache.resolve()), "CGO_ENABLED": "1", "CC": args.cc,
            "GOTOOLCHAIN": "local", "GOOS": "linux", "GOARCH": "amd64", "GOAMD64": "v1",
            "GOENV": "off", "GOPROXY": "off", "GOSUMDB": "off", "GOMAXPROCS": "2",
            "GOFLAGS": "", "GOWORK": "off",
        }
        command = [args.go, "build", "-p", "2", "-mod=readonly", "-buildvcs=false", "-trimpath",
                   "-buildmode=c-shared", "-ldflags=-buildid=", "-o", str(target), "."]
    result = execute(command, directory, check=bool(archive), flags=environment)
    if not archive:
        if result.returncode == 0 or "receiver" not in result.stderr:
            raise AssertionError((profile, "missing runtime was not diagnosed", result.stderr))
        return None
    return target


def oracle(vector):
    receiver, state, change, capabilities = vector
    if receiver not in (0, 1):
        return 1, state, (1,)
    if state not in range(256):
        return 2, state, (1,)
    if ((capabilities >> receiver) & 1) == 0:
        return 3, state, (1, 2)
    proposed = state + change * (1 if receiver == 0 else -1)
    events = (1, 2, 3 + receiver)
    if proposed not in range(256):
        return 4, state, events
    return 0, proposed, (*events, 5)


def observed(encoded):
    status = encoded >> 48
    state = encoded & MAX_U32
    trace = (encoded >> 32) & 0xffff
    events = tuple(int(digit, 16) for digit in f"{trace:x}")
    return status, state, events


def run_matrix(path, cases):
    library = ctypes.CDLL(str(path))
    probe = library.probe
    probe.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_int32, ctypes.c_uint32]
    probe.restype = ctypes.c_uint64
    profile = Counter()
    traces = sha256()
    for case in cases:
        encoded = probe(*case)
        actual = observed(encoded)
        expected = oracle(case)
        if actual != expected:
            raise AssertionError((path, case, actual, expected))
        profile[actual[0]] += 1
        traces.update(encoded.to_bytes(8, "little"))
    return {"observations": len(cases), "status_counts": dict(sorted(profile.items())),
            "native_trace_sha256": traces.hexdigest()}


def footprint(args, path, work):
    needed = re.findall(r"\(NEEDED\).*\[([^]]+)\]",
                        execute([args.readelf, "--dynamic", str(path)], work).stdout)
    symbols = execute([args.nm, "--defined-only", str(path)], work).stdout.splitlines()
    if not {"probe", "rt_dispatch"} <= {line.split()[-1] for line in symbols if line.strip()}:
        raise AssertionError((path, "missing linked runtime or probe symbol"))
    sections = execute([args.size, "-A", str(path)], work).stdout.splitlines()
    expected = {".text", ".rodata", ".data", ".bss"}
    sizes = {parts[0]: int(parts[1]) for line in sections if (parts := line.split()) and parts[0] in expected}
    return {"elf_bytes": path.stat().st_size, "selected_sections_bytes": sizes,
            "shared_libraries": needed, "static_runtime_symbol_linked": True}


def measure(args, work):
    archive = build_archive(args, work)
    cases = tuple(product((0, 1, 2, MAX_U32), STATES, CHANGES, GRANTS))
    builds = {}
    for profile in ADAPTER:
        binary = build_adapter(args, work / profile, profile, archive)
        facts = run_matrix(binary, cases)
        build_adapter(args, work / f"{profile}-missing-runtime", profile, None)
        stripped = binary.with_name("probe-without-debug.so")
        execute([args.strip, "--strip-debug", "-o", str(stripped), str(binary)], work)
        if run_matrix(stripped, cases) != facts:
            raise AssertionError((profile, "debug stripping changed observations"))
        builds[profile] = {
            **facts, **footprint(args, binary, work),
            "debug_stripped_elf_bytes": stripped.stat().st_size,
            "debug_stripped_observations": len(cases),
            "missing_runtime_link": "refused",
        }

    return {
        "tools": {label: execute([tool, "--version" if label != "go" else "version"], work).stdout.splitlines()[0]
                  for label, tool in (("cc", args.cc), ("cxx", args.cxx), ("go", args.go), ("rustc", args.rustc))},
        "provider_archive": {"bytes": archive.stat().st_size, "sha256": digest(archive)},
        "builds": builds,
        "observations": sum(row["observations"] + row["debug_stripped_observations"]
                            for row in builds.values()),
        "source_sha256": {path.name: digest(path) for path in
                          (HERE / "runtime.c", HERE / "runtime.h", HERE / "run.py",
                           *sorted(HERE.glob("adapter.*.in")))},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for flag, default in (("cc", "gcc"), ("cxx", "g++"), ("go", "go"), ("rustc", "rustc"),
                          ("readelf", "readelf"), ("ar", "ar"), ("nm", "nm"), ("size", "size"), ("strip", "strip")):
        parser.add_argument(f"--{flag}", default=default)
    parser.add_argument("--go-cache", type=Path, required=True)
    with TemporaryDirectory(prefix="llmlang-shared-c-runtime-") as work:
        print(json.dumps(measure(parser.parse_args(), Path(work)), indent=2))
