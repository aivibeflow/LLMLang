#!/usr/bin/env python3
"""Compare C default promotions and variadic call placement on five ABI profiles."""
import argparse
import importlib.util
from itertools import product
import json
from pathlib import Path
import struct
import tempfile


HERE = Path(__file__).resolve().parent
SHARED = HERE.parent / "FFI-AGGREGATE-CROSS-ABI-01" / "run.py"
spec = importlib.util.spec_from_file_location("cross_abi_tools", SHARED)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
PROFILES = {
    "sysv-x64": (["--target=x86_64-linux-gnu"], "elf_x86_64", 62, 0, None),
    "ms-x64-on-linux": (["--target=x86_64-linux-gnu", "-DMS_ABI"], "elf_x86_64", 62, 0, None),
    "linux-aarch64": (["--target=aarch64-linux-gnu"], "aarch64linux", 183, 0, "qemu_aarch64"),
    "rv64-lp64d": (["--target=riscv64-linux-gnu", "-march=rv64gc", "-mabi=lp64d", "-mno-relax"],
                   "elf64lriscv", 243, 5, "qemu_riscv64"),
    "rv64-lp64": (["--target=riscv64-linux-gnu", "-march=rv64gc", "-mabi=lp64", "-mno-relax"],
                  "elf64lriscv", 243, 1, "qemu_riscv64"),
}


def encode(file):
    values = (0.0, -0.0, -2.25, 0.1, 13.25, -0.3, 2.0**-149, 1e-23)
    integers = (-128, -127, -23, -1, 0, 1, 42, 127)
    tags = (0, 1, 0xdeadcaf123456789, 2**63, 2**64 - 1, 11, 999, 0x1122334455667788)
    inputs = []
    for round_index, (index, value) in product(range(3), enumerate(values)):
        rounded = struct.unpack("<f", struct.pack("<f", value))[0]
        inputs.append([0x32A40000 + round_index * 256 + index, integers[(index + round_index) % 8] % 2**64,
                       base.bits(value), base.bits(rounded), tags[(index + round_index) % 8]])
    lines = [".section .rodata", ".p2align 3", ".global input_count",
             "input_count: .quad " + str(len(inputs)), ".global input_vectors", "input_vectors:"]
    lines += [".quad " + ", ".join(hex(word) for word in row) for row in inputs]
    lines += ['.section .note.GNU-stack,"",%progbits']
    file.write_text("\n".join(lines) + "\n")
    expected = [[marker, small, rounded, tag] for marker, small, _, rounded, tag in inputs]
    return inputs, expected


def compile_with(args, flags, source, destination, arguments, environment):
    if source.suffix == ".c":
        arguments = [*arguments, "-std=c11", "-ffreestanding", "-fno-stack-protector",
                     "-fno-builtin", "-fno-pic", "-fno-pie", "-Wall", "-Wextra", "-Werror"]
    base.run([args.clang, *flags, *arguments, "-c", source, "-o", destination],
             destination.parent, environment)
    return destination


def study(args, root, name, optimization, input_file, inputs, expected, environment):
    flags, emulation, machine, expected_flags, launcher = PROFILES[name]
    work = root / f"{name}{optimization}"
    work.mkdir()
    build = lambda file, output, *options: compile_with(args, flags, file, work / (output + ".o"),
                                                       options, environment)
    provider = build(HERE / "provider.c", "provider", optimization)
    vectors = build(input_file, "vectors")
    syscalls = build(HERE / "syscalls.S", "syscalls")
    compiled = build(HERE / "consumer.c", "compiler-consumer", "-O2")
    caller = build(HERE / "consumer.c", "assembly-driver", "-O2", "-DASSEMBLY_CONSUMER")
    hand = build(HERE / "registers.S", "registers")
    wrong = build(HERE / "registers.S", "wrong-registers", "-DWRONG_FLOAT")
    not_narrowed = build(HERE / "consumer.c", "wide-source", "-O2", "-DWRONG_SOURCE_CARRIER")
    profiles = {
        "c": [compiled],
        "assembly": [caller, hand],
        "wrong-floating-register": [caller, wrong],
        "bypassed-float-conversion": [not_narrowed],
    }
    results = {}
    for route, objects in profiles.items():
        image = work / route
        base.run([args.lld, "-m", emulation, "-static", "-e", "_start", "-o", image,
                  *objects, provider, vectors, syscalls], work)
        flags_observed = base.read_elf(image, machine, expected_flags)
        command = [getattr(args, launcher), image] if launcher is not None else [image]
        raw = base.run(command, work).stdout
        observed = [list(values) for values in struct.iter_unpack("<4Q", raw)]
        assert len(observed) == len(expected)
        assert all(left[:2] == right[:2] and left[3] == right[3]
                   for left, right in zip(observed, expected))
        mismatches = [index for index, (left, right) in enumerate(zip(observed, expected)) if left != right]
        if route == "wrong-floating-register":
            assert len(mismatches) == len(expected)
            assert all(row[2] == base.bits(0.5) for row in observed)
        elif route == "bypassed-float-conversion":
            assert mismatches == [index for index, row in enumerate(inputs) if row[2] != row[3]]
            assert all(input_[2] == row[2] for input_, row in zip(inputs, observed))
        else:
            assert not mismatches
        results[route] = {"elf_flags": flags_observed, "image_sha256": base.fingerprint(image),
                          "observation_sha256": base.sha256(raw).hexdigest(),
                          "vectors": len(observed), "mismatching_indices": mismatches,
                          "observed_binary64": [row[2] for row in observed]}
    return {"routes": results, "provider_sha256": base.fingerprint(provider)}


def main():
    parser = argparse.ArgumentParser()
    for name in ("clang", "clang-libdir", "lld", "qemu-aarch64", "qemu-riscv64", "out"):
        parser.add_argument(f"--{name}", type=lambda path: Path(path).absolute(), required=name != "clang-libdir")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt13-variadic-") as scratch:
        root = Path(scratch)
        file = root / "vectors.S"
        inputs, expected = encode(file)
        environment = {**base.ENV, "LD_LIBRARY_PATH": str(args.clang_libdir)} if args.clang_libdir else base.ENV
        version = lambda program, env=base.ENV: base.run([program, "--version"], root, env).stdout.decode().splitlines()[0]
        versions = {"clang": version(args.clang, environment), "lld": version(args.lld),
                    "qemu-aarch64": version(args.qemu_aarch64), "qemu-riscv64": version(args.qemu_riscv64)}
        assert all("19.1.7" in version for version in (versions["clang"], versions["lld"]))
        assert all("10.0.13" in versions[key] for key in ("qemu-aarch64", "qemu-riscv64"))
        profiles = {f"{name}/{opt}": study(args, root, name, opt, file, inputs, expected, environment)
                    for name, opt in product(PROFILES, ("-O0", "-O2"))}
    args.out.write_text(json.dumps({"tools": versions, "inputs": inputs, "expected": expected,
                                    "profiles": profiles}, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
