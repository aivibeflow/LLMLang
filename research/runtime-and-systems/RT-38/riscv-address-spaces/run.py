#!/usr/bin/env python3
"""Compare address-space switching with the same freestanding RV64 IPC workload."""

import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory

from address_space import assembly, linker


HERE = Path(__file__).resolve().parent
IPC = HERE.parent / "riscv-ipc"
sys.path.insert(0, str(IPC))
SPEC = importlib.util.spec_from_file_location("rv64_ipc", IPC / "run.py")
ipc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ipc)
execute = ipc.execute
SCHEDULER = IPC.parent / "riscv-cooperative-scheduler"

QEMU_REVISION = "98f88efe8f07067667b8d9b1a5ce9551d34036c1"
CSR_SHA256 = "403918abb8cfe6ffe77f79f64ab673060b70f28830219538cfb3693a17deb3a1"


def source_scope(path):
    blob = path.read_bytes()
    if sha256(blob).hexdigest() != CSR_SHA256:
        raise ValueError("Expected the pinned QEMU target/riscv/csr.c blob")
    text = blob.decode("utf-8")
    legalize = text.split("static target_ulong legalize_xatp(", 1)[1].split("\n}", 1)[0]
    writer = text.split("static RISCVException write_satp(", 1)[1].split("\n}", 1)[0]
    if ("SATP64_MODE | SATP64_ASID | SATP64_PPN" not in legalize
            or "tlb_flush(env_cpu(env));" not in legalize
            or "env->satp = legalize_xatp(env, env->satp, val);" not in writer):
        raise ValueError("Missing QEMU satp-change flush implementation")
    return {"revision": QEMU_REVISION, "csr_sha256": CSR_SHA256, "flushes_on_changed_satp": True}


def check_switch(args, image, *, full_fence):
    text = execute(args.objdump, "-d", "--no-show-raw-insn", "--disassemble-symbols=install_translation", image)
    ops = [" ".join(op.split()) for op in re.findall(r"^\s*[0-9a-f]+:\s+([^\n]+)", text, re.MULTILINE)]
    common = ["srli t0, t0, 0xc", "or t0, t0, t2", "fence rw, rw", "csrw satp, t0"]
    expected = common + (["sfence.vma"] if full_fence else []) + ["csrr t1, satp"]
    if ops[:len(expected)] != expected or "mret" not in ops:
        raise ValueError(f"Unexpected linked switch in {image.name}")
    symbols = execute(args.nm, "--defined-only", image)
    names = ("root_a", "directory_a", "leaves_a", "root_b", "directory_b", "leaves_b")
    table_addresses = {name: 0x80004000 + index * 4096 for index, name in enumerate(names)}
    for name, address in {**table_addresses, "stack_a": 0x80201000, "stack_b": 0x80202000}.items():
        if not re.search(rf"^0*{address:x}\s+b\s+{name}$", symbols, re.MULTILINE):
            raise ValueError(f"Unexpected linked table or frame {name} in {image.name}")
    return {"translation_switch_instructions": expected,
            "page_tables": {name: hex(address) for name, address in table_addresses.items()},
            "page_table_bytes": len(table_addresses) * 4096}


def replay(args):
    scope = source_scope(args.qemu_csr_source)
    maximum = (1 << 64) - 1
    events = ipc.oracle(generation_checked=True, limit=maximum)
    expected = f"p{events[0]}q" + "".join(events[1:])
    profiles = {
        "shared_asid_full_fence": (0, True, expected),
        "distinct_asids": (1, False, expected),
        "aliased_worker_stacks": (2, True, f"p{events[0]}q{events[1]}K"),
        "peer_stack_user_alias": (3, True, "V"),
        "shared_asid_missing_fence": (4, False, expected),
    }
    with TemporaryDirectory(prefix="llmlang-rv64-address-spaces-") as temporary:
        work = Path(temporary)
        layout = work / "layout.ld"
        source = ipc.assembly((SCHEDULER / "boot.s").read_text(encoding="utf-8"))
        layout.write_text(linker(ipc.linker((SCHEDULER / "layout.ld").read_text(encoding="utf-8"))),
                          encoding="utf-8")
        c_obj = work / "ipc.o"
        execute(args.clang, "--target=riscv64-unknown-none-elf", "-march=rv64ima_zicsr", "-mabi=lp64",
                "-mcmodel=medany", "-mno-relax", "-ffreestanding", "-fno-builtin", "-fno-stack-protector",
                "-fno-unwind-tables", "-fno-asynchronous-unwind-tables", "-O2", "-Wall", "-Wextra", "-Werror",
                "-DGENERATIONS=1", f"-DGENERATION_MAX={maximum}UL", "-c", IPC / "ipc.c", "-o", c_obj)
        records = {}
        for name, (profile, full_fence, expected_trace) in profiles.items():
            asm = work / f"{name}.s"
            asm.write_text(assembly(source, profile), encoding="utf-8")
            obj, image = asm.with_suffix(".o"), asm.with_suffix(".elf")
            execute(args.mc, "-triple", "riscv64-unknown-none-elf", "-mattr=+zicsr,+zifencei",
                    "-filetype=obj", asm, "-o", obj)
            execute(args.lld, "--no-relax", "-T", layout, "-o", image, obj, c_obj)
            linked = ipc.check_image(args, image, generation_checked=True)
            switching = check_switch(args, image, full_fence=full_fence)
            uart = execute(args.qemu, "-machine", "virt", "-cpu", "rv64", "-m", "64M", "-smp", "1",
                           "-bios", "none", "-nodefaults", "-display", "none", "-monitor", "none",
                           "-serial", "stdio", "-kernel", image)
            if uart != expected_trace:
                raise ValueError(f"Expected {expected_trace!r} for {name}, observed {uart!r}")
            records[name] = {**linked, **switching, "asids": [0, int(profile == 1)], "uart": uart}
    if len({record["user_sha256"] for record in records.values()}) != 1:
        raise ValueError("User code or message vectors changed across address-space alternatives")
    inputs = {f"scheduler-{name}": SCHEDULER / name for name in ("boot.s", "layout.ld", "run.py")}
    inputs.update((f"ipc-{name}", IPC / name) for name in ("adapt.py", "ipc.c", "reference.py", "request_vectors.py", "run.py"))
    inputs.update((name, HERE / name) for name in ("address_space.py", "run.py"))
    return {"schema": "llmlang-rt38-rv64-address-spaces-v1", "machine": "virt", "harts": 1, "qemu_scope": scope,
            "tools": {name: execute(getattr(args, name), "--version").splitlines()[0].strip()
                      for name in ("clang", "mc", "lld", "objdump", "qemu")},
            "input_sha256": {name: sha256(path.read_bytes()).hexdigest() for name, path in inputs.items()},
            "images": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, command in {
        "clang": "clang-19", "mc": "llvm-mc-19", "lld": "ld.lld-19", "readelf": "llvm-readelf-19",
        "nm": "llvm-nm-19", "objcopy": "llvm-objcopy-19", "objdump": "llvm-objdump-19", "qemu": "qemu-system-riscv64",
    }.items():
        parser.add_argument(f"--{name}", default=command)
    parser.add_argument("--qemu-csr-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(replay(args), indent=2) + "\n", encoding="utf-8")
