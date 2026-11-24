#!/usr/bin/env python3
"""Replay two RV64 principals using a one-element IPC endpoint."""

import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from adapt import assembly, linker
from reference import replay as oracle


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "riscv-cooperative-scheduler"
SPEC = importlib.util.spec_from_file_location("rv64_scheduler", BASE / "run.py")
scheduler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scheduler)
execute = scheduler.execute


PROFILES = {
    "check_generation": (True, (1 << 64) - 1),
    "slot_identity_only": (False, (1 << 64) - 1),
    "retire_after_second_grant": (True, 2),
}


def check_image(args, image, *, generation_checked):
    headers = execute(args.readelf, "-W", "-h", "-l", image)
    if (not re.search(r"Machine:\s+RISC-V", headers)
            or not re.search(r"Entry point address:\s+0x80000000\b", headers)
            or not re.search(r"Type:\s+EXEC\b", headers)
            or re.search(r"^\s+(INTERP|DYNAMIC)\b", headers, re.MULTILINE)
            or execute(args.nm, "--undefined-only", image).strip()):
        raise ValueError(f"Expected a freestanding RV64 program: {image.name}")

    loads = []
    for line in headers.splitlines():
        fields = line.split()
        if fields and fields[0] == "LOAD":
            address, physical, file_size, size = map(lambda value: int(value, 16), fields[2:6])
            if address != physical or file_size > size:
                raise ValueError(f"Invalid static load at {line}")
            loads.append((address, "".join(fields[6:-1]), file_size, size))
    if [(address, flags) for address, flags, _, _ in loads] != scheduler.LOADS:
        raise ValueError(f"Unexpected permissions or extent: {loads}")
    if not (loads[1][0] + loads[1][3] < 0x80200000 and loads[3][3] == 8192):
        raise ValueError("Kernel state overlaps the user PMP boundary")
    symbols = execute(args.nm, "--defined-only", image)
    if not re.search(r"^0*80001000 d endpoint$", symbols, re.MULTILINE):
        raise ValueError("IPC endpoint state moved outside the expected load")

    user = image.with_suffix(".user")
    execute(args.objcopy, "-O", "binary", "-j", ".user", image, user)
    return {"elf_sha256": sha256(image.read_bytes()).hexdigest(),
            "user_sha256": sha256(user.read_bytes()).hexdigest(),
            "kernel_text_bytes": loads[0][2], "kernel_state_bytes": loads[1][3],
            "checks_generation": generation_checked}


def replay(args):
    with TemporaryDirectory(prefix="llmlang-rv64-ipc-") as temporary:
        work = Path(temporary)
        source, layout, kernel = (work / name for name in ("boot.s", "layout.ld", "boot.o"))
        source.write_text(assembly((BASE / "boot.s").read_text(encoding="utf-8")), encoding="utf-8")
        layout.write_text(linker((BASE / "layout.ld").read_text(encoding="utf-8")), encoding="utf-8")
        execute(args.mc, "-triple", "riscv64-unknown-none-elf", "-mattr=+zicsr,+zifencei",
                "-filetype=obj", source, "-o", kernel)
        records = {}
        for name, (generation_checked, limit) in PROFILES.items():
            obj, image = (work / f"{name}.{ext}" for ext in ("o", "elf"))
            execute(args.clang, "--target=riscv64-unknown-none-elf", "-march=rv64ima_zicsr", "-mabi=lp64",
                    "-mcmodel=medany", "-mno-relax", "-ffreestanding", "-fno-builtin", "-fno-stack-protector",
                    "-fno-unwind-tables", "-fno-asynchronous-unwind-tables", "-O2", "-Wall", "-Wextra", "-Werror",
                    f"-DGENERATIONS={int(generation_checked)}", f"-DGENERATION_MAX={limit}UL", "-c", HERE / "ipc.c",
                    "-o", obj)
            execute(args.lld, "--no-relax", "-T", layout, "-o", image, kernel, obj)
            linked = check_image(args, image, generation_checked=generation_checked)
            events = oracle(generation_checked=generation_checked, limit=limit)
            observed = execute(args.qemu, "-machine", "virt", "-cpu", "rv64", "-m", "64M", "-smp", "1",
                               "-bios", "none", "-nodefaults", "-display", "none", "-monitor", "none",
                               "-serial", "stdio", "-kernel", image)
            if observed != "".join(events):
                raise ValueError(f"Divergent UART trace in {name}: {observed!r}, expected {''.join(events)!r}")
            records[name] = {**linked, "max_generation": limit, "events": events, "uart": observed}
    if len({record["user_sha256"] for record in records.values()}) != 1:
        raise ValueError("Expected identical U-mode programs")
    baseline = records["check_generation"]["events"]
    broken = records["slot_identity_only"]["events"]
    retired = records["retire_after_second_grant"]["events"]
    if (baseline[13:16] != ["BS", "AE", "BA"] or broken[13:16] != ["BA", "Af", "BA"]
            or baseline[20:25] != ["AG", "BS", "AE", "BA", "Ak"]
            or retired[20:25] != ["AO", "BN", "AE", "BN", "AE"]):
        raise ValueError("The expected stale-send or retirement witness changed")
    files = {f"base-{name}": BASE / name for name in ("boot.s", "layout.ld", "run.py")}
    files.update((name, HERE / name) for name in ("ipc.c", "adapt.py", "reference.py", "request_vectors.py", "run.py"))
    return {"schema": "llmlang-rt38-rv64-ipc-v1", "machine": "virt", "harts": 1,
            "tools": {name: execute(getattr(args, name), "--version").splitlines()[0].strip()
                      for name in ("clang", "mc", "lld", "qemu")},
            "input_sha256": {name: sha256(path.read_bytes()).hexdigest() for name, path in files.items()},
            "images": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, command in {
        "clang": "clang-19", "mc": "llvm-mc-19", "lld": "ld.lld-19", "readelf": "llvm-readelf-19",
        "nm": "llvm-nm-19", "objcopy": "llvm-objcopy-19", "qemu": "qemu-system-riscv64",
    }.items():
        parser.add_argument(f"--{name}", default=command)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(replay(args), indent=2) + "\n", encoding="utf-8")
