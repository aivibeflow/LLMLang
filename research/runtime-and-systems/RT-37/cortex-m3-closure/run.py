#!/usr/bin/env python3
"""Compare explicit Cortex-M3 runtime closure and booted behavior."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import select
import struct
import sys
import subprocess
from tempfile import TemporaryDirectory
from time import monotonic

HERE = Path(__file__).resolve().parent
FLASH_LIMIT = 256 * 1024
RAM_BASE = 0x20000000
RAM_LIMIT = RAM_BASE + 64 * 1024
TARGET = "thumbv7m-none-eabi"


def run(arguments, **options):
    return subprocess.run([str(arg) for arg in arguments], capture_output=True, text=True, timeout=45, **options)


def output(arguments):
    return run(arguments, check=True).stdout


def assemble(command, source, target):
    output([command, "-triple", TARGET, "-filetype=obj", source, "-o", target])


def compile_llvm(command, source, target, level):
    output([command, f"-O={level}", f"-mtriple={TARGET}", "-mcpu=cortex-m3", "-filetype=obj",
            source, "-o", target])


def compile_rust(command, source, target, level):
    output([command, "--target", TARGET, "--crate-type=lib", "--emit=obj", "-C", f"opt-level={level}",
            "-C", "overflow-checks=yes", "-C", "panic=abort", source, "-o", target])


def link(command, image, objects, *, missing=None):
    result = run([command, "-T", HERE / "memory.ld", "--gc-sections", "-Map", image.with_suffix(".map"),
                  "-o", image, *objects])
    if missing is None:
        result.check_returncode()
        return
    if result.returncode == 0 or missing not in result.stderr:
        raise ValueError(f"Expected an unresolved {missing} when linking {image.name}\n{result.stderr}")


def boot(command, image):
    arguments = [command, "-machine", "lm3s6965evb", "-cpu", "cortex-m3", "-nodefaults", "-display", "none",
                 "-monitor", "none", "-serial", "stdio", "-kernel", str(image)]
    with subprocess.Popen(arguments, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE) as process:
        received = bytearray()
        deadline = monotonic() + 8
        try:
            while received[-1:] not in (b"!", b"X"):
                remaining = deadline - monotonic()
                if remaining <= 0 or not select.select([process.stdout], [], [], remaining)[0]:
                    raise ValueError(f"No boot completion marker from {image.name}: {received!r}")
                chunk = os.read(process.stdout.fileno(), 256)
                if not chunk:
                    raise ValueError(f"Emulator exited before {image.name} completed: {received!r}")
                received.extend(chunk)
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                pending, diagnostics = process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                pending, diagnostics = process.communicate()
        received.extend(pending)
        messages = diagnostics.decode().splitlines()
        unexpected = [line for line in messages if "terminating on signal" not in line
                      and "nic stellaris_enet.0 has no peer" not in line]
        if unexpected:
            raise ValueError(f"Unexpected emulator diagnostics for {image.name}: {unexpected}")
        return received.decode()


def inspect(args, image):
    headers = output([args.readelf, "-W", "-h", "-l", image])
    if not re.search(r"Machine:\s+ARM\b", headers) or not re.search(r"Type:\s+EXEC\b", headers):
        raise ValueError(f"Expected a bare-metal ARM executable: {image.name}")
    if re.search(r"^\s+(INTERP|DYNAMIC)\b", headers, re.MULTILINE) or output(
        [args.nm, "--undefined-only", image]
    ).strip():
        raise ValueError(f"Unexpected hosted or unresolved runtime dependency: {image.name}")

    segments = []
    for line in headers.splitlines():
        values = line.split()
        if values and values[0] == "LOAD":
            _, virtual, physical, file_size, memory_size = (int(value, 16) for value in values[1:6])
            flags = "".join(values[6:-1])
            if file_size > memory_size or ("W" in flags and "E" in flags):
                raise ValueError(f"Invalid load segment flags or length for {image.name}")
            if file_size and physical + file_size > FLASH_LIMIT:
                raise ValueError(f"Load image exceeds flash for {image.name}")
            if virtual < RAM_BASE:
                if virtual != physical or virtual + memory_size > FLASH_LIMIT:
                    raise ValueError(f"Flash segment is out of bounds for {image.name}")
            elif virtual + memory_size > RAM_LIMIT:
                raise ValueError(f"RAM segment is out of bounds for {image.name}")
            segments.append({"virtual": virtual, "physical": physical, "file_bytes": file_size,
                             "memory_bytes": memory_size, "flags": flags})
    flash = [row["physical"] + row["file_bytes"] for row in segments if row["file_bytes"]]
    ram = [row["virtual"] + row["memory_bytes"] for row in segments if RAM_BASE <= row["virtual"] < RAM_LIMIT]
    if not flash or not ram or max(flash) > FLASH_LIMIT or max(ram) > RAM_LIMIT:
        raise ValueError(f"Invalid loadable image ranges for {image.name}")
    vector_bytes = image.with_suffix(".vectors.bin")
    output([args.objcopy, "-O", "binary", "-j", ".vectors", image, vector_bytes])
    stack, reset = struct.unpack_from("<II", vector_bytes.read_bytes())
    entry = re.search(r"Entry point address:\s+(0x[\da-f]+)", headers, re.IGNORECASE)
    if stack != RAM_LIMIT or not reset & 1 or not entry or reset != int(entry[1], 16):
        raise ValueError(f"Wrong Cortex-M vector layout for {image.name}")
    return {"flash_extent_bytes": max(flash), "static_ram_bytes": max(ram) - RAM_BASE,
            "reset_vector": hex(reset), "initial_stack": hex(stack),
            "loads": segments,
            "image_sha256": sha256(image.read_bytes()).hexdigest()}


def reference(cases):
    duty = 250
    results = []
    for sample, valid in cases:
        if valid != 1 or sample >= 100:
            duty = 0
        elif sample >= 80:
            duty = min(255, duty + 13)
        elif sample < 20:
            duty = max(0, duty - 9)
        results.append(duty)
    return "B" + "".join(f" {value:02x}" for value in results) + "!"


def compare(args):
    cases = json.loads((HERE / "inputs.json").read_text())
    expected = reference(cases)
    with TemporaryDirectory(prefix="llmlang-cortex-m3-") as scratch:
        work = Path(scratch)
        fixture = work / "samples.s"
        fixture.write_text('\n'.join(('.section .rodata.fixture,"a",%progbits', '.balign 4',
                                     '.global fixture_begin, fixture_end', 'fixture_begin:',
                                     *(f'.word {sample}, {valid}' for sample, valid in cases),
                                     'fixture_end:', '')))
        start, samples = work / "startup.o", work / "samples.o"
        assemble(args.mc, HERE / "startup.s", start)
        assemble(args.mc, fixture, samples)
        records = {}
        methods = {"llvm": (compile_llvm, args.llc, HERE / "step.ll"),
                   "rust": (compile_rust, args.rustc, HERE / "step.rs")}
        for backend, (compile_object, compiler, source) in methods.items():
            for level in (0, 2):
                name = f"{backend}-O{level}"
                obj, image = work / f"{name}.o", work / f"{name}.elf"
                compile_object(compiler, source, obj, level)
                link(args.lld, image, (start, samples, obj))
                memory = inspect(args, image)
                observed = boot(args.qemu, image)
                if observed != expected:
                    raise ValueError(f"Trace mismatch for {name}: {observed!r} != {expected!r}")
                records[name] = {**memory, "uart": observed}

        ordinary = work / "ordinary.rs"
        ordinary.write_text((HERE / "step.rs").read_text().replace("previous.saturating_add(13)", "(previous + 13)"))
        panic = work / "checked-add.o"
        compile_rust(args.rustc, ordinary, panic, 0)
        link(args.lld, work / "panic.elf", (start, samples, panic), missing="panic_const_add_overflow")
        optimized = work / "checked-add-O2.o"
        opt_image = work / "checked-add-O2.elf"
        compile_rust(args.rustc, ordinary, optimized, 2)
        link(args.lld, opt_image, (start, samples, optimized))
        if boot(args.qemu, opt_image) != expected:
            raise ValueError("Optimized ordinary addition changed the fixture observations")
        records["rust-checked-add-O2"] = {**inspect(args, opt_image), "uart": expected}

        unwind = work / "unspecified-unwind.ll"
        unwind.write_text((HERE / "step.ll").read_text().replace(" nounwind", ""))
        unwind_obj, unwind_image = work / "unwind.o", work / "unwind.elf"
        compile_llvm(args.llc, unwind, unwind_obj, 0)
        link(args.lld, unwind_image, (start, samples, unwind_obj))
        if "__aeabi_unwind_cpp_pr0" not in output([args.nm, "--undefined-only", unwind_image]):
            raise ValueError("Leaving unwind behavior implicit did not emit the expected symbol")
        if boot(args.qemu, unwind_image) != expected:
            raise ValueError("Unwind control did not reach the expected trace")

        wide = work / "division.o"
        compile_llvm(args.llc, HERE / "wide_division.ll", wide, 2)
        link(args.lld, work / "division.elf", (start, samples, wide), missing="__aeabi_uldivmod")

        no_zero_source, no_zero = work / "skip-zero.s", work / "skip-zero.o"
        no_zero_source.write_text((HERE / "startup.s").read_text().replace("  str r2, [r0], #4", "  adds r0, #4"))
        assemble(args.mc, no_zero_source, no_zero)
        no_zero_image = work / "no-zero.elf"
        link(args.lld, no_zero_image, (no_zero, samples, work / "llvm-O2.o"))
        if boot(args.qemu, no_zero_image) != "X":
            raise ValueError("Skipping zero initialization did not fail the boot check")

    tools = {name: output([getattr(args, name), "--version"]).splitlines()[0].strip()
             for name in ("mc", "llc", "lld", "readelf", "nm", "objcopy", "rustc", "qemu")}
    return {
        "schema": "llmlang-freestanding-cortex-m3-v1",
        "tool_versions": tools,
        "rustc_build": output([args.rustc, "-vV"]).strip(),
        "python": sys.version,
        "target": TARGET,
        "machine": "lm3s6965evb",
        "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest() for name in (
            "inputs.json", "startup.s", "memory.ld", "step.ll", "step.rs", "wide_division.ll", "run.py")},
        "steps_per_image": len(cases),
        "images": records,
        "controls": {"rust_checked_add_O0": "panic_const_add_overflow",
                     "llvm_wide_division_O2": "__aeabi_uldivmod",
                     "llvm_unspecified_unwind_O0": "__aeabi_unwind_cpp_pr0",
                     "skip_bss_zero": "X"},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, command in {
        "mc": "llvm-mc-19", "llc": "llc-19", "lld": "ld.lld-19", "readelf": "llvm-readelf-19",
        "nm": "llvm-nm-19", "objcopy": "llvm-objcopy-19", "rustc": "rustc", "qemu": "qemu-system-arm",
    }.items():
        parser.add_argument(f"--{name}", default=command)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    data = compare(args)
    args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"{len(data['images'])} booted images, {data['steps_per_image']} observed steps per image")
