"""Check replacement frame publication during one preemptible RV64 wait."""

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
IPC = HERE.parent / "RV64-PREEMPTIVE-IPC-01"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def command(*args):
    result = subprocess.run(args, capture_output=True, check=True, text=True, timeout=15)
    assert not result.stderr, result.stderr
    return result.stdout


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def collect(args, work):
    timer = load("timer_transform", TIMER / "transform.py")
    ipc = load("ipc_transform", IPC / "compose.py")
    start = timer.render((COOPERATIVE / "boot.s").read_text(encoding="utf-8"), 0, 0, 1, 1)
    base = ipc.render(start, 1, 0)
    profiles = {
        "sanitized_replacement": (0, "WIBCARba!"),
        "dirty_publication": (1, "WIBCM"),
        "publish_old_frame": (2, "WIBCO"),
        "wake_before_mapping": (3, "WIBCF"),
    }
    qemu = [args.qemu]
    if args.qemu_data:
        qemu += ["-L", args.qemu_data]
    rows = {}
    for name, (control, expected) in profiles.items():
        asm = work / f"{name}.s"
        asm.write_text(render(base, control), encoding="utf-8")
        obj, elf, user = (asm.with_suffix(ext) for ext in (".o", ".elf", ".user"))
        command(args.mc, "-triple", "riscv64-unknown-none-elf", "-mattr=+zicsr,+zifencei",
                "-filetype=obj", asm, "-o", obj)
        command(args.lld, "--no-undefined", "--no-relax", "-T", COOPERATIVE / "layout.ld",
                obj, "-o", elf)
        header = command(args.readelf, "-hW", "-lW", "-rW", elf)
        assert not re.search(r"(?m)^\s+(INTERP|DYNAMIC)\b", header)
        assert "There are no relocations" in header
        assert not command(args.nm, "--undefined-only", elf).strip()
        symbols = {
            label: int(address, 16) for address, _, label in
            (row.split() for row in command(args.nm, "--defined-only", elf).splitlines())
        }
        assert symbols["replacement_frame"] == symbols["old_frame"] + 4096
        assert symbols["replacement_live"] == symbols["replacement_frame"] + 4096
        call = command(args.objdump, "-d", "--no-show-raw-insn", elf)
        replacement = call.split("<replace_lease>:\n", 1)[1].split("<private_page_fault>:\n", 1)[0]
        assert replacement.count("sfence.vma") == (1 if control == 3 else 2)
        command(args.objcopy, "-O", "binary", "-j", ".user", elf, user)
        observed = command(
            *qemu, "-machine", "virt", "-cpu", "rv64", "-m", "64M", "-smp", "1",
            "-bios", "none", "-nodefaults", "-display", "none", "-monitor", "none",
            "-serial", "stdio", "-icount", "shift=0,align=off,sleep=off", "-kernel", elf,
        )
        assert observed == expected, (name, observed)
        rows[name] = {
            "uart": observed, "elf_sha256": digest(elf), "user_sha256": digest(user),
            "old_frame": hex(symbols["old_frame"]), "replacement_frame": hex(symbols["replacement_frame"]),
            "translation_fences_in_transaction": replacement.count("sfence.vma"),
        }
    assert len({row["user_sha256"] for row in rows.values()}) == 1
    return {
        "qemu": command(args.qemu, "--version").splitlines()[0],
        "qemu_sha256": digest(Path(shutil.which(args.qemu)).resolve()),
        "llvm": command(args.mc, "--version").splitlines()[0],
        "sources": {
            f"{path.parent.name}/{path.name}": digest(path)
            for path in (HERE / "run.py", HERE / "compose.py", HERE / "replace.s.in",
                         TIMER / "transform.py", COOPERATIVE / "boot.s", COOPERATIVE / "layout.ld",
                         IPC / "compose.py", *sorted(IPC.glob("*.s.in")))
        },
        "profiles": rows,
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
    with tempfile.TemporaryDirectory(prefix="rt38-live-frame-") as scratch:
        evidence = collect(args, Path(scratch))
    args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
