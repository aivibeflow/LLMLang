"""Replay blocked IPC and exact two-root context switching on single-hart RV64."""

import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from compose import render


HERE = Path(__file__).resolve().parent
COOPERATIVE = HERE.parent / "riscv-cooperative-scheduler"
TIMER = HERE.parent / "RV64-TIMER-PREEMPTION-01"


def reference(revoke):
    """Observe task progress, the live generation and the receiver's continuation."""
    runnable = {"A", "B"}
    endpoint = 1
    runnable.remove("A")
    events = ["W"]
    assert sorted(runnable) == ["B"]
    events.append("B")
    disposition = 17 if revoke else 41
    if revoke:
        endpoint += 1
    runnable.add("A")
    events.extend(["C" if disposition == 17 else "D", "A"])
    if revoke:
        assert endpoint != 1
        events.append("R")
    runnable.remove("B")
    runnable.remove("A")
    assert not runnable
    return "".join(events) + "ba!"


def call(*args):
    result = subprocess.run(args, capture_output=True, text=True, check=True, timeout=15)
    assert not result.stderr, result.stderr
    return result.stdout


def hash_file(path):
    return sha256(path.read_bytes()).hexdigest()


def collect(args, root):
    spec = importlib.util.spec_from_file_location("timer_transform", TIMER / "transform.py")
    timer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(timer)
    common = timer.render((COOPERATIVE / "boot.s").read_text(encoding="utf-8"), 0, 0, 1, 1)
    profiles = (
        ("deliver", 0, 0, reference(False)),
        ("revoke", 1, 0, reference(True)),
        ("run_blocked", 0, 1, "WBT"),
        ("alias_private_stack", 0, 2, "WBDK"),
        ("accept_stale_generation", 1, 3, "WBCART"),
    )
    qemu = [args.qemu]
    if args.qemu_data:
        qemu.extend(["-L", args.qemu_data])
    observed = {}
    for name, mode, mutant, expected in profiles:
        asm = root / f"{name}.s"
        asm.write_text(render(common, mode, mutant), encoding="utf-8")
        obj, elf = asm.with_suffix(".o"), asm.with_suffix(".elf")
        call(args.mc, "-triple", "riscv64-unknown-none-elf", "-mattr=+zicsr,+zifencei",
             "-filetype=obj", asm, "-o", obj)
        call(args.lld, "--no-undefined", "--no-relax", "-T", COOPERATIVE / "layout.ld",
             obj, "-o", elf)
        headers = call(args.readelf, "-hW", "-lW", "-rW", elf)
        assert "There are no relocations" in headers
        assert not re.search(r"(?m)^\s+(INTERP|DYNAMIC)\b", headers)
        assert not call(args.nm, "--undefined-only", elf).strip()
        assert re.search(r"Entry point address:\s+0x80000000", headers)
        symbols = call(args.nm, "--defined-only", elf)
        mapped = {}
        for address, _, symbol in (row.split() for row in symbols.splitlines() if row.strip()):
            if symbol.startswith(("root_", "directory_", "leaves_", "stack_")):
                mapped[symbol] = int(address, 16)
        roots = ("root_a", "directory_a", "leaves_a", "root_b", "directory_b", "leaves_b")
        assert [mapped[name] for name in roots] == list(range(0x80002000, 0x80008000, 4096))
        assert (mapped["stack_a"], mapped["stack_b"]) == (0x80201000, 0x80202000)
        disassembly = call(args.objdump, "-d", "--no-show-raw-insn", elf)
        translation = disassembly.split("<install_root>:\n", 1)[1].split("<park_timer>:\n", 1)[0]
        assert re.search(r"csrw\s+satp, t0.*sfence.vma.*csrr\s+t1, satp", translation, re.S)
        user = elf.with_suffix(".user")
        call(args.objcopy, "-O", "binary", "-j", ".user", elf, user)
        trace = call(
            *qemu, "-machine", "virt", "-cpu", "rv64", "-m", "64M", "-smp", "1",
            "-bios", "none", "-nodefaults", "-display", "none", "-monitor", "none",
            "-serial", "stdio", "-icount", "shift=0,align=off,sleep=off", "-kernel", elf,
        )
        assert trace == expected, (name, trace, expected)
        observed[name] = {
            "elf_sha256": hash_file(elf), "user_sha256": hash_file(user),
            "page_table_and_stack_symbols": {name: hex(address) for name, address in mapped.items()},
            "uart": trace,
        }
    assert len({row["user_sha256"] for row in observed.values()}) == 1
    sources = (
        HERE / "compose.py", HERE / "run.py", *sorted(HERE.glob("*.s.in")),
        COOPERATIVE / "boot.s", COOPERATIVE / "layout.ld", TIMER / "transform.py",
    )
    return {
        "source_pins": {
            f"{source.parent.name}/{source.name}": hash_file(source) for source in sources
        },
        "profile": "RV64 QEMU single hart, two Sv39 roots, timer and blocked IPC",
        "llvm_version": call(args.mc, "--version").splitlines()[0],
        "qemu_version": call(args.qemu, "--version").splitlines()[0],
        "qemu_sha256": hash_file(Path(shutil.which(args.qemu)).resolve()),
        "observations": observed,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, binary in (
        ("mc", "llvm-mc-19"), ("lld", "ld.lld-19"), ("readelf", "llvm-readelf-19"),
        ("nm", "llvm-nm-19"), ("objdump", "llvm-objdump-19"), ("objcopy", "llvm-objcopy-19"),
        ("qemu", "qemu-system-riscv64"),
    ):
        parser.add_argument(f"--{name}", default=binary)
    parser.add_argument("--qemu-data", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt38-preemptive-ipc-") as scratch:
        evidence = collect(args, Path(scratch))
    args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
