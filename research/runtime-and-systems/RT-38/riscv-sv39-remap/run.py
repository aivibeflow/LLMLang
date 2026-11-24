#!/usr/bin/env python3
"""Observe Sv39 remap/revoke with correct, missing and mis-scoped fences."""

import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from transform import render


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "riscv-trap-isolation"
SPEC = importlib.util.spec_from_file_location("rv64_trap_isolation", BASE / "run.py")
isolation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(isolation)
execute = isolation.execute

QEMU_REVISION = "98f88efe8f07067667b8d9b1a5ce9551d34036c1"
QEMU_PINS = {
    "target/riscv/insn_trans/trans_privileged.c.inc": "5545cc55241d4be2dcb7317c7a3143b2c5dcbfc33568f3a012cb379eb8e8c345",
    "target/riscv/op_helper.c": "7afcac2a94b2615fe99077f18794075c454a8fc9480595fca53e80290ae77aee",
}
PROFILES = {
    "whole_hart": (0, "BEISRAMBDPZ!", ("sfence.vma",)),
    "right_virtual_address": (1, "BEISRAMBDPZ!", ("lui t0, 0x40400", "sfence.vma t0")),
    "unrelated_virtual_address": (2, "BEISRAMBDPZ!", ("lui t0, 0x40401", "sfence.vma t0")),
    "only_memory_fence": (3, "BEISRAMADA!", ()),
}


def qemu_scope(directory):
    source = {}
    for name, expected in QEMU_PINS.items():
        blob = (directory / name).read_bytes()
        if sha256(blob).hexdigest() != expected:
            raise ValueError(f"Unexpected upstream QEMU source for {name}")
        source[name] = blob.decode("utf-8")
    translator = source["target/riscv/insn_trans/trans_privileged.c.inc"]
    helper = source["target/riscv/op_helper.c"]
    function = translator.split("static bool trans_sfence_vma(", 1)[1].split("\n}", 1)[0]
    implementation = helper.split("void helper_tlb_flush(", 1)[1].split("\n}", 1)[0]
    if "gen_helper_tlb_flush(tcg_env);" not in function or "a->" in function or "tlb_flush(cs);" not in implementation:
        raise ValueError("Expected the pinned operand-insensitive TLB flush path")
    return {"revision": QEMU_REVISION, "source_sha256": QEMU_PINS, "address_operand_used": False}


def linked_fence(args, image, expected):
    disassembly = execute(args.objdump, "-d", "--no-show-raw-insn", "--disassemble-symbols=synchronize_translation", image)
    if "<synchronize_translation>:" not in disassembly:
        raise ValueError(f"Missing update routine for {image.name}")
    instructions = tuple(" ".join(op.split()) for op in re.findall(r"^\s*[0-9a-f]+:\s+([^\n]+)",
                                                                      disassembly, flags=re.MULTILINE))
    if instructions != ("fence rw, rw", *expected, "ret"):
        raise ValueError(f"Unexpected update instructions in {image.name}: {instructions}")
    symbols = execute(args.nm, "--defined-only", image)
    if not re.search(r"^0*80401000\s+D\s+replacement_frame$", symbols, flags=re.MULTILINE):
        raise ValueError(f"Replacement-frame address changed in {image.name}")
    return instructions


def replay(args):
    sources = qemu_scope(args.qemu_source)
    source = (BASE / "boot.s").read_text(encoding="utf-8")
    with TemporaryDirectory(prefix="llmlang-rv64-remap-") as tmp:
        work = Path(tmp)
        records = {}
        for name, (policy, expected, instruction) in PROFILES.items():
            asm = work / f"{name}.s"
            asm.write_text(render(source, policy), encoding="utf-8")
            obj, image = asm.with_suffix(".o"), asm.with_suffix(".elf")
            execute(args.mc, "-triple", "riscv64-unknown-none-elf", "-mattr=+zicsr,+zifencei",
                    "-filetype=obj", asm, "-o", obj)
            execute(args.lld, "--no-relax", "-T", BASE / "memory.ld", "-o", image, obj)
            exact = isolation.check_elf(args, image, paged=True)
            if exact["loads"][-1]["file_bytes"] != 4104:
                raise ValueError(f"Unexpected source or replacement frame load for {image.name}")
            operations = linked_fence(args, image, instruction)
            observed = execute(args.qemu, "-machine", "virt", "-cpu", "rv64", "-m", "64M", "-smp", "1",
                               "-bios", "none", "-nodefaults", "-display", "none", "-monitor", "none",
                               "-serial", "stdio", "-kernel", image)
            if observed != expected:
                raise ValueError(f"Expected {name} {expected!r}, observed {observed!r}")
            probe_physical = int(exact["symbols"]["user_probe"], 16)
            probe_virtual = 0x40000000 + probe_physical - isolation.USER_CODE
            records[name] = {"elf_sha256": exact["elf_sha256"], "user_code_sha256": exact["user_code_sha256"],
                             "user_probe_physical": hex(probe_physical), "user_probe_virtual": hex(probe_virtual),
                             "update_instructions": operations,
                             "uart": observed}
    if len({record["user_code_sha256"] for record in records.values()}) != 1:
        raise ValueError("User code differs across fence policies")
    inputs = {"base-boot.s": BASE / "boot.s", "base-memory.ld": BASE / "memory.ld", "base-run.py": BASE / "run.py",
              "transform.py": HERE / "transform.py", "run.py": Path(__file__)}
    return {"schema": "llmlang-rt38-sv39-remap-v1", "machine": "virt", "cpu": "rv64", "harts": 1,
            "qemu_scope": sources, "tools": {name: execute(getattr(args, name), "--version").splitlines()[0].strip()
                                             for name in ("mc", "lld", "objdump", "qemu")},
            "input_sha256": {name: sha256(path.read_bytes()).hexdigest() for name, path in inputs.items()},
            "images": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, command in {
        "mc": "llvm-mc-19", "lld": "ld.lld-19", "readelf": "llvm-readelf-19", "nm": "llvm-nm-19",
        "objcopy": "llvm-objcopy-19", "objdump": "llvm-objdump-19", "qemu": "qemu-system-riscv64",
    }.items():
        parser.add_argument(f"--{name}", default=command)
    parser.add_argument("--qemu-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(replay(args), indent=2) + "\n", encoding="utf-8")
