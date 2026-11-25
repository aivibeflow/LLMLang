"""Replay the exact RT-10 file and spawn probes under two static libc profiles."""

import argparse
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
FILE_PROBE = HERE.parent / "POSIX-FILE-IDENTITY-01"
SPAWN_PROBE = HERE.parent / "POSIX-SPAWN-DESCRIPTORS-01"
DIRECTORY = "x86_64-linux-musl"


def import_runner(path, name):
    spec = importlib.util.spec_from_file_location(name, path / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def invoke(command, directory):
    return subprocess.run(command, cwd=directory, check=True, capture_output=True, text=True,
                          timeout=60, env={**os.environ, "LC_ALL": "C"}).stdout


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def musl_specs(root, directory):
    dev = root / "usr" / "lib" / DIRECTORY
    source = dev / "musl-gcc.specs"
    template = source.read_text(encoding="utf-8")
    include_root = root / "usr" / "include" / DIRECTORY
    if not (include_root / "spawn.h").is_file() or not (dev / "libc.a").is_file():
        raise ValueError("The pinned musl development sysroot is incomplete")
    text = template.replace(f"/usr/include/{DIRECTORY}", str(include_root))
    text = text.replace(f"/usr/lib/{DIRECTORY}", str(dev))
    adapted = directory / "musl-relocated.specs"
    adapted.write_text(text, encoding="utf-8")
    return adapted, dev / "libc.a", digest(source)


def checked_binary(args, work, profile, library, options, fixture, opt):
    path = work / f"{fixture.name.lower()}-{profile}-O{opt}"
    link = invoke([args.cc, *options, "-std=c17", "-Wall", "-Wextra", "-Werror",
                   "-static", "-Wl,-t", f"-O{opt}", str(fixture / "probe.c"), "-o", str(path)], work)
    libc_paths = {Path(line).resolve() for line in link.splitlines() if line.endswith("/libc.a")}
    if libc_paths != {library.resolve()}:
        raise ValueError((profile, libc_paths, library))
    elf = invoke([args.readelf, "--program-headers", "--dynamic", str(path)], work)
    if "INTERP" in elf or "(NEEDED)" in elf:
        raise ValueError((profile, "unexpected shared runtime dependency"))
    return path


def assess(args, work):
    file = import_runner(FILE_PROBE, "rt10_file_identity")
    spawn = import_runner(SPAWN_PROBE, "rt10_spawn_descriptors")
    gcc_lib = Path(invoke([args.cc, "-print-file-name=libc.a"], work).strip())
    specs, musl_lib, original_specs = musl_specs(args.musl_root.resolve(), work)
    profiles = {
        "glibc": (gcc_lib, ()),
        "musl": (musl_lib, (f"-specs={specs}",)),
    }
    builds = {}
    total_checked = 0
    for libc, (archive, options) in profiles.items():
        for opt in (0, 2):
            file_binary = checked_binary(args, work, libc, archive, options, FILE_PROBE, opt)
            spawn_binary = checked_binary(args, work, libc, archive, options, SPAWN_PROBE, opt)
            for repeat in range(4):
                case = work / f"{libc}-O{opt}-{repeat}"
                case.mkdir()
                file_rows = invoke([str(file_binary)], case).splitlines()
                if len(file_rows) != len(file.EXPECTED) or dict(row.split("=", 1) for row in file_rows) != file.EXPECTED:
                    raise AssertionError((libc, opt, repeat, file_rows))
                source = case / "input"
                source.write_bytes(b"ABCDEFGH")
                found_spawn = spawn.parse(invoke([str(spawn_binary), str(source)], case))
                if found_spawn != spawn.EXPECTED:
                    raise AssertionError((libc, opt, repeat, found_spawn))
                total_checked += len(file.EXPECTED) + len(spawn.EXPECTED)
            builds[f"{libc}-O{opt}"] = {
                "runtime_archive_sha256": digest(archive),
                "file_binary_sha256": digest(file_binary),
                "spawn_binary_sha256": digest(spawn_binary),
                "repetitions": 4,
            }

    return {
        "compiler": invoke([args.cc, "--version"], work).splitlines()[0],
        "target": invoke([args.cc, "-dumpmachine"], work).strip(),
        "libc_glibc_profile": os.confstr("CS_GNU_LIBC_VERSION"),
        "musl_original_specs_sha256": original_specs,
        "kernel": platform.release(),
        "filesystem": invoke(["stat", "-f", "-c", "%T", str(work)], work).strip(),
        "verified_file_fields_per_repetition": len(file.EXPECTED),
        "verified_spawn_cases_per_repetition": len(spawn.EXPECTED),
        "checks_across_profiles": total_checked,
        "builds": builds,
        "source_sha256": {path.relative_to(HERE.parent).as_posix(): digest(path)
                          for path in (HERE / "run.py", FILE_PROBE / "probe.c",
                                       FILE_PROBE / "run.py", SPAWN_PROBE / "probe.c",
                                       SPAWN_PROBE / "run.py")},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--readelf", default="readelf")
    parser.add_argument("--musl-root", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-posix-cross-libc-") as temporary:
        print(json.dumps(assess(args, Path(temporary)), indent=2))


if __name__ == "__main__":
    main()
