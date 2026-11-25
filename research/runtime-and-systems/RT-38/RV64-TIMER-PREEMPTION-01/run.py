"""Boot timer-driven RV64 tasks and verify the context and scheduling observations."""

import argparse
from collections import deque
from hashlib import sha256
import importlib.util
from itertools import product
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from transform import render


HERE = Path(__file__).resolve().parent
COOPERATIVE = HERE.parent / "riscv-cooperative-scheduler"


def reference(budgets, reschedule):
    queue = deque((0, 1))
    credits = list(budgets)
    trace = []
    while queue:
        task = queue.popleft()
        if credits[task] == 0:
            trace.append("ab"[task])
        else:
            credits[task] -= 1
            trace.append("AB"[task])
            if reschedule:
                queue.append(task)
            else:
                queue.appendleft(task)
    return "".join(trace) + "!"


def command(*args):
    result = subprocess.run(args, capture_output=True, check=True, text=True, timeout=15)
    assert not result.stderr, result.stderr
    return result.stdout


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def collect(args, work):
    spec = importlib.util.spec_from_file_location("cooperative_scope", COOPERATIVE / "run.py")
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    original = (COOPERATIVE / "boot.s").read_text(encoding="utf-8")
    proof = command(args.lean, HERE / "Progress.lean")
    assert proof.count("does not depend on any axioms") == 2
    assert proof.count("depends on axioms: [propext]") == 2
    assert len(proof.splitlines()) == 4
    profiles = [
        (name, policy, 0, budgets, reference(budgets, policy == 0))
        for (name, policy), budgets in product(
            (("round_robin", 0), ("keep_current", 1)), ((1, 1), (1, 3), (3, 1), (3, 3)),
        )
    ]
    profiles.extend([
        ("saved_register_fault", 0, 1, (3, 3), "ABS"),
        ("wrong_continuation", 0, 2, (3, 3), "ABT"),
    ])
    qemu = [args.qemu]
    if args.qemu_data:
        qemu.extend(["-L", args.qemu_data])
    records = {}
    for name, policy, mutation, budgets, expected in profiles:
        label = f"{name}-{budgets[0]}-{budgets[1]}"
        source = work / f"{label}.s"
        source.write_text(render(original, policy, mutation, *budgets), encoding="utf-8")
        obj = source.with_suffix(".o")
        image = source.with_suffix(".elf")
        command(args.mc, "-triple", "riscv64-unknown-none-elf", "-mattr=+zicsr,+zifencei",
                "-filetype=obj", source, "-o", obj)
        command(args.lld, "--no-undefined", "--no-relax", "-T", COOPERATIVE / "layout.ld",
                obj, "-o", image)
        facts = previous.linked_metadata(args, image, 0)
        assert "There are no relocations" in command(args.readelf, "-rW", image)
        instructions = command(args.objdump, "-d", "--no-show-raw-insn", image)
        timer = instructions.split("<timer>:\n", 1)[1].split("<stopping>:\n", 1)[0]
        assert re.search(r"\bsd\s+t2, 0x80\(sp\)", timer)
        user = instructions.split("<user_entry>:\n", 1)[1]
        assert len(re.findall(r"(?m)^\s*[a-f0-9]+:\s+ecall\s*$", user)) == 2
        assert "<user_yield>" not in user
        observed = command(
            *qemu, "-machine", "virt", "-cpu", "rv64", "-m", "64M", "-smp", "1",
            "-bios", "none", "-nodefaults", "-display", "none", "-monitor", "none",
            "-serial", "stdio", "-icount", "shift=0,align=off,sleep=off", "-kernel", image,
        )
        assert observed == expected, (label, expected, observed)
        records[label] = {**facts, "timer_credits": budgets, "uart": observed}
    assert len({row["user_code_sha256"] for row in records.values()}) == 1
    return {
        "qemu_version": command(args.qemu, "--version").splitlines()[0],
        "qemu_sha256": digest(Path(shutil.which(args.qemu)).resolve()),
        "llvm_version": command(args.mc, "--version").splitlines()[0],
        "lean_version": command(args.lean, "--version").splitlines()[0],
        "proof_audit": proof.splitlines(),
        "machine": "QEMU virt RV64 single hart, no firmware, fixed virtual instruction clock",
        "sources": {
            f"{path.parent.name}/{path.name}": digest(path)
            for path in (HERE / "run.py", HERE / "transform.py", HERE / "Progress.lean", COOPERATIVE / "boot.s",
                         COOPERATIVE / "layout.ld", COOPERATIVE / "run.py")
        },
        "profiles": records,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, binary in (
        ("mc", "llvm-mc-19"), ("lld", "ld.lld-19"), ("readelf", "llvm-readelf-19"),
        ("nm", "llvm-nm-19"), ("objdump", "llvm-objdump-19"), ("objcopy", "llvm-objcopy-19"),
        ("qemu", "qemu-system-riscv64"), ("lean", "lean"),
    ):
        parser.add_argument(f"--{name}", default=binary)
    parser.add_argument("--qemu-data", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt38-rv64-timer-") as scratch:
        ledgers = collect(args, Path(scratch))
    args.output.write_text(json.dumps(ledgers, indent=2, sort_keys=True) + "\n", encoding="utf-8")
