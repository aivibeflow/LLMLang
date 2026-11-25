"""Run a common Linux FFI provider and callback contract on three execution profiles."""

import argparse
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
SOURCE_FILES = ("abi.h", "provider.c", "host.c")
AGES = (0, 1, 0x8000000000000000, 0xffffffffffffffff)
STATES = (0, 1, 67, 68, 99, 100, 101, 0xffffffff)
DELTAS = (0, 1, 2, 31, 32, 33, 0xffffffff)
PROFILES = {
    "x86_64": ("x86_64-linux-gnu", 62, "ld-linux-x86-64.so.2", ()),
    "aarch64": ("aarch64-linux-gnu", 183, "ld-linux-aarch64.so.1", ()),
    "riscv64": ("riscv64-linux-gnu", 243, "ld-linux-riscv64-lp64d.so.1", ("-march=rv64gc", "-mabi=lp64d")),
}


def command(*args, cwd=None, checked=True):
    env = {**os.environ, "LC_ALL": "C"}
    env.pop("LD_PRELOAD", None)
    return subprocess.run(
        args, cwd=cwd, env=env, text=True, capture_output=True, check=checked, timeout=30,
    )


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def expected():
    outcomes = []
    for generation, state, delta in product(AGES, STATES, DELTAS):
        next_state = state + delta
        if delta <= 32 and next_state <= 100:
            outcomes.append(((generation + 1) % 2**64, next_state, 0, 2, 11, delta, 23, next_state))
        else:
            outcomes.append((generation, state, 1, 2, 11, delta, 29, state))
    return outcomes


def machine(artifact):
    header = artifact.read_bytes()[:24]
    assert header.startswith(b"\x7fELF\x02\x01")
    return struct.unpack_from("<H", header, 18)[0]


def needed(args, artifact):
    facts = command(args.readelf, "-dW", artifact).stdout
    return set(re.findall(r"\(NEEDED\).*\[([^]]+)\]", facts))


def compile_profile(args, work, name, foreign, runner, target, code, interpreter, options):
    for filename in SOURCE_FILES:
        shutil.copyfile(HERE / filename, work / filename)
    library_root = Path("/usr/lib/x86_64-linux-gnu") if foreign is None else foreign / "lib"
    loader = library_root / interpreter
    libc = library_root / "libc.so.6"
    assert machine(loader) == machine(libc) == code
    headers = [] if foreign is None else ["-isystem", foreign / "include"]
    flags = [args.clang, f"--target={target}", *options, *headers, "-std=c17", "-O2", "-fPIC",
             "-Wall", "-Wextra", "-Werror"]
    for source, obj, extra in (
        ("provider.c", "provider.o", []),
        ("provider.c", "mutated.o", ["-DOMIT_COMMIT_EVENT"]),
        ("host.c", "host.o", []),
    ):
        command(*flags, *extra, "-c", source, "-o", obj, cwd=work)
    command(args.ar, "rcsD", "libtransition.a", "provider.o", cwd=work)
    for source, shared in (("provider.o", "libtransition.so"), ("mutated.o", "libmutated.so")):
        command(args.linker, "-shared", "--no-undefined", "-soname", shared, source, "-o", shared, cwd=work)
        assert machine(work / shared) == code and not needed(args, work / shared)
    cohorts = {
        "static-provider": "libtransition.a",
        "shared-provider": "libtransition.so",
        "same_abi_omitted_event": "libmutated.so",
    }
    out = {}
    reference = expected()
    for route, provider in cohorts.items():
        artifact = work / route
        interpreter_path = ("/lib64/" if name == "x86_64" else "/lib/") + interpreter
        command(
            args.linker, "--no-undefined", "--dynamic-linker", interpreter_path, "-rpath", "$ORIGIN",
            library_root / "crt1.o", library_root / "crti.o", "host.o", provider,
            libc, "--as-needed", loader, library_root / "crtn.o", "-o", artifact, cwd=work,
        )
        assert machine(artifact) == code
        imports = needed(args, artifact)
        assert imports == ({"libc.so.6"} if route == "static-provider" else {"libc.so.6", provider}), (name, imports)
        assert interpreter_path in command(args.readelf, "-lW", artifact).stdout
        launcher = [] if runner is None else [runner, "-L", foreign]
        result = command(*launcher, artifact, cwd=work)
        assert not result.stderr, result.stderr
        binding, *rows = result.stdout.splitlines()
        heading, resolved_provider, resolved_libc, reported = binding.split()
        assert heading == "binding" and reported == "2.41"
        expected_provider = artifact if route == "static-provider" else work / provider
        assert Path(resolved_provider).resolve() == expected_provider.resolve()
        target_libc_path = Path(resolved_libc)
        if foreign is not None:
            target_libc_path = foreign / target_libc_path.as_posix().lstrip("/")
        assert digest(target_libc_path.resolve()) == digest(libc)
        actual = [tuple(map(int, line.split())) for line in rows]
        assert len(reference) == len(actual) == 224
        all_bad = sum(wanted != observed for wanted, observed in zip(reference, actual))
        scalar_bad = sum(wanted[:3] != observed[:3] for wanted, observed in zip(reference, actual))
        expected_bad = sum(row[2] == 0 for row in reference) if route == "same_abi_omitted_event" else 0
        assert all_bad == expected_bad and scalar_bad == 0
        out[route] = {
            "artifact_sha256": digest(artifact), "provider_sha256": digest(expected_provider),
            "observations": len(rows), "complete_mismatches": all_bad,
            "scalar_mismatches": scalar_bad, "needed": sorted(imports),
            "trace_sha256": sha256("\n".join(rows).encode("ascii")).hexdigest(),
        }
    return {
        "target": target, "elf_machine": code, "architecture_flags": options,
        "execution": "native" if runner is None else "qemu-linux-user",
        "emulator_sha256": None if runner is None else digest(runner),
        "glibc": "2.41", "glibc_sha256": digest(libc), "loader_sha256": digest(loader),
        "startup_sha256": {name: digest(library_root / name) for name in ("crt1.o", "crti.o", "crtn.o")},
        "routes": out,
    }


def collect(args, work):
    linux = {
        "x86_64": (None, None),
        "aarch64": (args.arm64_root, args.qemu_aarch64),
        "riscv64": (args.rv64_root, args.qemu_riscv64),
    }
    reports = {}
    for name, (root, runner) in linux.items():
        used = work / name
        used.mkdir()
        reports[name] = compile_profile(args, used, name, root, runner, *PROFILES[name])
    assert len({r["routes"]["shared-provider"]["trace_sha256"] for r in reports.values()}) == 1
    assert len({r["routes"]["static-provider"]["trace_sha256"] for r in reports.values()}) == 1
    assert all(r["routes"]["shared-provider"]["trace_sha256"] == r["routes"]["static-provider"]["trace_sha256"]
               for r in reports.values())
    wrong_arch = command(
        args.linker, "-shared", "-o", work / "wrong.so",
        work / "aarch64/provider.o", work / "riscv64/provider.o", checked=False,
    )
    assert wrong_arch.returncode and "incompatible with" in wrong_arch.stderr
    return {
        "profiles": reports,
        "cross_architecture_object_control": "refused",
        "tools": {
            name: command(getattr(args, name), "--version").stdout.splitlines()[0]
            for name in ("clang", "linker", "ar", "readelf", "qemu_aarch64", "qemu_riscv64")
        },
        "sources": {name: digest(HERE / name) for name in ("run.py", *SOURCE_FILES)},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for label, tool in (("clang", "clang"), ("linker", "ld.lld"), ("ar", "llvm-ar"), ("readelf", "readelf")):
        parser.add_argument(f"--{label}", default=tool)
    for label in ("arm64-root", "rv64-root", "qemu-aarch64", "qemu-riscv64"):
        parser.add_argument(f"--{label}", required=True, type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt13-ffi-linux-") as directory:
        evidence = collect(args, Path(directory))
    args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
