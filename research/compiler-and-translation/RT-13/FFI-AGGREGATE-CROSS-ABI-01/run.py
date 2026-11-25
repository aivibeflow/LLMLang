#!/usr/bin/env python3
"""Reproduce selected AArch64 and RV64 aggregate calls through QEMU user mode."""
import argparse
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
ENV = {key: value for key, value in os.environ.items() if not key.startswith(("LD_", "QEMU_"))}
ENV.update({"LC_ALL": "C", "TZ": "UTC"})
PROFILES = {
    "aarch64-aapcs64": (
        ["--target=aarch64-linux-gnu"], "aarch64.S", "aarch64linux", "aarch64", 0,
    ),
    "rv64-lp64d": (
        ["--target=riscv64-linux-gnu", "-march=rv64gc", "-mabi=lp64d", "-mno-relax", "-DHARD_FLOAT"],
        "riscv64.S", "elf64lriscv", "riscv64", 5,
    ),
    "rv64-lp64": (
        ["--target=riscv64-linux-gnu", "-march=rv64gc", "-mabi=lp64", "-mno-relax"],
        "riscv64.S", "elf64lriscv", "riscv64", 1,
    ),
}


def run(command, cwd, env=ENV, *, check=True):
    process = subprocess.run(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=20)
    if check:
        assert process.returncode == 0, (command, process.stdout.decode(errors="replace"),
                                         process.stderr.decode(errors="replace"))
    return process


def fingerprint(path):
    return sha256(path.read_bytes()).hexdigest()


def bits(value):
    return struct.unpack("<Q", struct.pack("<d", value))[0]


def generate_vectors(file):
    masks = (0, 1, 0xfedcba9876543210, 0x8000000000000000, 0x1122334455667788, 0xffffffffffffffff)
    floating = (0.0, -0.0, -1.5, 0.25, 17.0, -42.0, 2.0**52, -(2.0**52))
    cases = [
        (measure, masks[(index + shift * 3) % len(masks)],
         floating[(index + shift) % len(floating)], floating[-index - 1],
         masks[(index + 2) % len(masks)], masks[(index + shift + 3) % len(masks)])
        for shift, (index, measure) in product(range(3), enumerate(floating))
    ]
    assert len(cases) == 24
    inputs = [[bits(measure), tag, bits(first), bits(second), left, right]
              for measure, tag, first, second, left, right in cases]
    observations = [[bits(measure + 1.5), tag ^ 0x13579bdf, bits(first + 2.0),
                     bits(-second), left, right, left ^ right]
                    for measure, tag, first, second, left, right in cases]
    lines = [".section .rodata", ".p2align 3",
             ".global input_count", "input_count: .quad " + str(len(cases)),
             ".global input_vectors", "input_vectors:"]
    lines += [".quad " + ", ".join(hex(word) for word in words) for words in inputs]
    lines += [".global input_end", "input_end:", '.section .note.GNU-stack,"",%progbits']
    file.write_text("\n".join(lines) + "\n")
    return inputs, observations


def compile_one(args, profile, source, destination, *, extra=()):
    target_flags = PROFILES[profile][0]
    environment = {**ENV, "LD_LIBRARY_PATH": str(args.clang_libdir)} if args.clang_libdir else ENV
    initial = [args.clang, *target_flags, *extra, "-c"]
    if source.suffix == ".c":
        initial += ["-std=c11", "-ffreestanding", "-fno-builtin", "-fno-stack-protector",
                    "-fno-pic", "-fno-pie", "-Wall", "-Wextra", "-Werror"]
    run([*initial, source, "-o", destination], destination.parent, environment)


def read_elf(path, machine, expected_flags):
    data = path.read_bytes()
    assert data[:6] == bytes.fromhex("7f454c460201")
    assert struct.unpack_from("<H", data, 18)[0] == machine
    flags = struct.unpack_from("<I", data, 48)[0]
    assert flags == expected_flags, (path.name, flags)
    inspection = run(["readelf", "-lW", path], path.parent).stdout.decode()
    assert "INTERP" not in inspection and "DYNAMIC" not in inspection
    return flags


def link(args, profile, output, inputs):
    linker_format = PROFILES[profile][2]
    return run([args.lld, "-m", linker_format, "-static", "-e", "_start",
                "-o", output, *inputs], output.parent, check=False)


def observe(args, profile, root, emulator, opt, inputs, expected):
    _, assembler, _, architecture, elf_flags = PROFILES[profile]
    directory = root / f"{profile}{opt}"
    directory.mkdir()
    sources = {
        "provider": (HERE / "provider.c", [opt]),
        "assembly": (HERE / assembler, []),
        "wrong": (HERE / assembler, ["-DWRONG_MIXED"]),
        "c": (HERE / "consumer.c", ["-O2"]),
        "syscalls": (HERE / "syscalls.S", []),
        "vectors": (inputs, []),
    }
    objects = {}
    for name, (source, options) in sources.items():
        objects[name] = directory / f"{name}.o"
        compile_one(args, profile, source, objects[name], extra=options)
    outcomes = {}
    for name in ("c", "assembly", "wrong"):
        executable = directory / name
        artifacts = [objects[key] for key in (name, "provider", "syscalls", "vectors")]
        result = link(args, profile, executable, artifacts)
        assert result.returncode == 0, result.stderr.decode()
        flags = read_elf(executable, 183 if architecture == "aarch64" else 243, elf_flags)
        output = run([emulator, executable], directory).stdout
        received = [list(row) for row in struct.iter_unpack("<7Q", output)]
        assert len(received) == len(expected)
        if name == "wrong":
            errors = [index for index, (source, actual) in enumerate(zip(expected, received))
                      if source[:2] != actual[:2]]
            assert all(source[2:] == actual[2:] for source, actual in zip(expected, received))
            assert len(errors) == len(expected), errors
            outcomes[name] = {"mixed_mismatch": errors, "actual_mixed": [row[:2] for row in received]}
        else:
            assert received == expected
            outcomes[name] = {"matched": len(received), "observation_sha256": sha256(output).hexdigest()}
        outcomes[name].update({"executable_sha256": fingerprint(executable), "elf_flags": flags})
    return {"provider_object_sha256": fingerprint(objects["provider"]),
            "routes": outcomes}, objects


def main():
    parser = argparse.ArgumentParser()
    for name in ("clang", "clang-libdir", "lld", "qemu-aarch64", "qemu-riscv64", "out"):
        # Preserve the ld.lld filename because this multicall executable chooses its driver from argv[0].
        parser.add_argument(f"--{name}", type=lambda path: Path(path).absolute(), required=name != "clang-libdir")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt13-cross-abi-") as scratch:
        root = Path(scratch)
        vectors = root / "vectors.S"
        inputs, expected = generate_vectors(vectors)
        qemu = {"aarch64": args.qemu_aarch64, "riscv64": args.qemu_riscv64}
        build_env = {**ENV, "LD_LIBRARY_PATH": str(args.clang_libdir)} if args.clang_libdir else ENV
        versions = {
            "clang": run([args.clang, "--version"], root, build_env).stdout.decode().splitlines()[0],
            "lld": run([args.lld, "--version"], root).stdout.decode().splitlines()[0],
            **{arch: run([command, "--version"], root).stdout.decode().splitlines()[0]
               for arch, command in qemu.items()},
        }
        assert "19.1.7" in versions["clang"] and "19.1.7" in versions["lld"]
        assert all("10.0.13" in versions[arch] for arch in qemu)
        profiles, object_files = {}, {}
        for profile, opt in product(PROFILES, ("-O0", "-O2")):
            observation, objects = observe(args, profile, root, qemu[PROFILES[profile][3]],
                                           opt, vectors, expected)
            profiles[profile, opt] = observation
            object_files[profile, opt] = objects
        hard = object_files["rv64-lp64d", "-O2"]
        soft = object_files["rv64-lp64", "-O2"]
        incompatible = link(args, "rv64-lp64d", root / "wrong-link",
                            [hard["assembly"], soft["provider"], hard["syscalls"], hard["vectors"]])
        assert incompatible.returncode and b"different floating-point ABI" in incompatible.stderr, (
            incompatible.stderr.decode())
        result = {"tool_versions": versions, "inputs_as_words": inputs, "expected_as_words": expected,
                  "linked_abi_mismatch": "LLD refused object files with different floating-point ABI",
                  "profiles": {f"{name}/{opt}": observation
                               for (name, opt), observation in profiles.items()}}
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
