#!/usr/bin/env python3
"""Compare physical and virtual protection in the pinned single-hart RV64 fixture."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import struct
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
PROFILES = {
    "bare_wide_pmp": (0, "BEIWV!"),
    "bare_single_tor": (1, "BEIWFZ!"),
    "sv39_supervisor_page": (2, "BEISRPZ!"),
    "sv39_user_bit_control": (3, "BEISRV!"),
    "bare_split_tor": (4, "BEITRFZ!"),
}
LOAD_MAP = {
    0x80000000: "RE", 0x80001000: "RW", 0x80200000: "RE", 0x80201000: "RW", 0x80400000: "RW",
}
PAGE_SIZE = 4096
USER_CODE = 0x80200000
MACHINE_MEMORY_END = 0x84000000


def execute(*arguments):
    command = list(map(str, arguments))
    result = subprocess.run(command, capture_output=True, text=True, timeout=25)
    if result.returncode or result.stderr:
        raise ValueError(f"Unexpected tool result for {command}: {result.returncode} {result.stdout!r} {result.stderr!r}")
    return result.stdout


def check_elf(args, image, *, paged):
    headers = execute(args.readelf, "-W", "-h", "-l", "-s", image)
    if not re.search(r"Machine:\s+RISC-V", headers) or not re.search(r"Entry point address:\s+0x80000000\b", headers):
        raise ValueError(f"Unexpected RV64 entry in {image.name}")
    if not re.search(r"Type:\s+EXEC\b", headers) or re.search(r"^\s+(INTERP|DYNAMIC)\b", headers, re.MULTILINE):
        raise ValueError(f"Expected a freestanding image for {image.name}")
    if execute(args.nm, "--undefined-only", image).strip():
        raise ValueError(f"Unexpected unresolved dependency in {image.name}")

    segments = {}
    for line in headers.splitlines():
        columns = line.split()
        if not columns or columns[0] != "LOAD":
            continue
        _, virtual, physical, file, memory = map(lambda value: int(value, 16), columns[1:6])
        flags = "".join(columns[6:-1])
        if (virtual in segments or virtual != physical or flags != LOAD_MAP.get(virtual) or memory < file
                or virtual % PAGE_SIZE or virtual + memory > MACHINE_MEMORY_END):
            raise ValueError(f"Unexpected load geometry for {image.name}: {line}")
        segments[virtual] = {"address": hex(virtual), "file_bytes": file, "memory_bytes": memory, "flags": flags}
    if set(segments) != set(LOAD_MAP):
        raise ValueError(f"Missing an expected region in {image.name}")
    ordered = sorted(segments)
    if any(current + segments[current]["memory_bytes"] > following
           for current, following in zip(ordered, ordered[1:])):
        raise ValueError(f"Overlapping load regions for {image.name}")
    kernel_state_bytes = (5 if paged else 1) * PAGE_SIZE
    if segments[0x80001000]["memory_bytes"] != kernel_state_bytes:
        raise ValueError(f"Unexpected page-table or stack extent for {image.name}")

    symbol_names = ("trap", "machine_stack_top", "user_entry", "user_stack_top",
                    "user_store", "user_probe", "user_rx_marker", "protected_word")
    if paged:
        symbol_names += ("root_table",)
    symbols = {name: int(address, 16) for address, name in re.findall(
        rf"^\s*\d+:\s+([a-f0-9]+)\s+\d+\s+\w+\s+\w+\s+\w+\s+\d+\s+({'|'.join(symbol_names)})$",
        headers, flags=re.MULTILINE)}
    if set(symbols) != set(symbol_names) or symbols["user_entry"] != USER_CODE:
        raise ValueError(f"Incomplete symbol map for {image.name}")
    if (not 0x80000000 <= symbols["trap"] < 0x80001000 or (paged and symbols["root_table"] != 0x80001000)
            or symbols["machine_stack_top"] != 0x80001000 + kernel_state_bytes
            or symbols["user_stack_top"] != 0x80202000
            or symbols["protected_word"] != 0x80400000):
        raise ValueError(f"A link-time privilege boundary changed in {image.name}")

    user = image.with_suffix(".user.bin")
    execute(args.objcopy, "-O", "binary", "-j", ".user", image, user)
    instructions = user.read_bytes()
    for name, opcode in (("user_store", 0x23), ("user_probe", 0x03)):
        offset = symbols[name] - USER_CODE
        if offset < 0 or offset % 4 or offset + 4 > len(instructions):
            raise ValueError(f"Unexpected {name} position for {image.name}")
        (encoded,) = struct.unpack_from("<I", instructions, offset)
        if encoded & 0x7F != opcode or (encoded >> 12) & 7 != 3:
            raise ValueError(f"Expected a four-byte RV64 doubleword access for {name}")
    return {"elf_sha256": sha256(image.read_bytes()).hexdigest(), "loads": list(segments.values()),
            "user_code_sha256": sha256(instructions).hexdigest(), "kernel_state_bytes": kernel_state_bytes,
            "symbols": {name: hex(address) for name, address in symbols.items()}}


def replay(args):
    qemu_base = [args.qemu]
    if args.qemu_data is not None:
        qemu_base += ["-L", args.qemu_data]
    qemu_base += ["-machine", "virt", "-cpu", "rv64", "-m", "64M", "-smp", "1", "-bios", "none",
                  "-nodefaults", "-display", "none", "-monitor", "none", "-serial", "stdio"]
    with TemporaryDirectory(prefix="llmlang-riscv-isolation-") as tmp:
        work = Path(tmp)
        records = {}
        for name, (profile, expected) in PROFILES.items():
            source = work / f"{name}.s"
            code = (HERE / "boot.s").read_text(encoding="utf-8")
            source.write_text(f".set PROFILE, {profile}\n" + code, encoding="utf-8")
            obj, image = source.with_suffix(".o"), source.with_suffix(".elf")
            execute(args.mc, "-triple", "riscv64-unknown-none-elf", "-mattr=+zicsr,+zifencei",
                    "-filetype=obj", source, "-o", obj)
            execute(args.lld, "--no-relax", "-T", HERE / "memory.ld", "-o", image, obj)
            metadata = check_elf(args, image, paged=profile in (2, 3))
            observed = execute(*qemu_base, "-kernel", image)
            if observed != expected:
                raise ValueError(f"Expected {name} to emit {expected!r}, got {observed!r}")
            records[name] = {**metadata, "uart": observed}
    if len({record["user_code_sha256"] for record in records.values()}) != 1:
        raise ValueError("The user code differs across protection profiles")
    return {"schema": "llmlang-rt38-rv64-trap-isolation-v1", "machine": "virt", "cpu": "rv64", "harts": 1,
            "tools": {name: execute(getattr(args, name), "--version").splitlines()[0].strip()
                      for name in ("mc", "lld", "readelf", "qemu")},
            "input_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                             for name in ("boot.s", "memory.ld", "run.py")},
            "images": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, command in {
        "mc": "llvm-mc-19", "lld": "ld.lld-19", "readelf": "llvm-readelf-19", "nm": "llvm-nm-19",
        "objcopy": "llvm-objcopy-19", "qemu": "qemu-system-riscv64",
    }.items():
        parser.add_argument(f"--{name}", default=command)
    parser.add_argument("--qemu-data", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(replay(args), indent=2) + "\n", encoding="utf-8")
