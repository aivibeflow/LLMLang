#!/usr/bin/env python3
"""Compare cooperative scheduling and linked RV64 integer context records."""

import argparse
from collections import deque
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
LOADS = [(0x80000000, "RE"), (0x80001000, "RW"), (0x80200000, "RE"), (0x80201000, "RW")]
INTEGER_REGISTERS = ("zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2", "s0", "s1",
                     "a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7", "s2", "s3", "s4",
                     "s5", "s6", "s7", "s8", "s9", "s10", "s11", "t3", "t4", "t5", "t6")
WORKLOADS = ((1, 1), (1, 3), (3, 1), (3, 3))


def reference(workload, *, round_robin):
    runnable = deque(range(len(workload)))
    remaining = list(workload)
    events = []
    while runnable:
        task = runnable.popleft()
        if remaining[task] == 0:
            events.append("ab"[task])
            continue
        events.append("AB"[task])
        remaining[task] -= 1
        if round_robin:
            runnable.append(task)
        else:
            runnable.appendleft(task)
    return "".join(events) + "!"


def interleaving_wait(trace):
    runnable = {"A": 0, "B": 0}
    worst_wait = dict(runnable)
    for event in trace[:-1]:
        task = event.upper()
        worst_wait[task] = max(worst_wait[task], runnable[task])
        if event.isupper():
            runnable[task] = 0
            for waiting in runnable.keys() - {task}:
                runnable[waiting] += 1
        else:
            del runnable[task]
    return worst_wait


def linked_metadata(args, image, policy):
    headers = execute(args.readelf, "-W", "-h", "-l", image)
    if (not re.search(r"Machine:\s+RISC-V", headers)
            or not re.search(r"Entry point address:\s+0x80000000\b", headers)
            or not re.search(r"Type:\s+EXEC\b", headers)
            or re.search(r"^\s+(INTERP|DYNAMIC)\b", headers, re.MULTILINE)
            or execute(args.nm, "--undefined-only", image).strip()):
        raise ValueError(f"Invalid freestanding image {image.name}")
    loads = []
    for line in headers.splitlines():
        columns = line.split()
        if not columns or columns[0] != "LOAD":
            continue
        address, physical, file_bytes, memory_bytes = (int(value, 16) for value in columns[2:6])
        flags = "".join(columns[6:-1])
        if address != physical or memory_bytes >= 0x100000 or file_bytes > memory_bytes:
            raise ValueError(f"Unexpected linked load in {image.name}: {line}")
        loads.append((address, flags, file_bytes, memory_bytes))
    if ([(address, flags) for address, flags, _, _ in loads] != LOADS
            or [loads[1][3], loads[3][3]] != [544, 8192]
            or loads[0][3] > 4096 or loads[2][3] > 4096):
        raise ValueError(f"Unexpected segment geometry: {loads}")
    symbols = execute(args.nm, "--defined-only", image)
    for name, address in {"context_a": 0x80001000, "context_b": 0x80001100, "user_entry": 0x80200000,
                          "stack_a": 0x80201000, "stack_b": 0x80202000, "stack_b_top": 0x80203000}.items():
        if not re.search(rf"^0*{address:x}\s+\w\s+{name}$", symbols, re.MULTILINE):
            raise ValueError(f"Missing linked state or U-mode boundary for {name}")
    trap = execute(args.objdump, "-d", "--no-show-raw-insn", "--disassemble-symbols=trap", image)
    resume = execute(args.objdump, "-d", "--no-show-raw-insn", image).split("<resume>:\n", 1)[1]
    resume = resume.split("<report_user_fault>:\n", 1)[0]
    for index, register in enumerate(INTEGER_REGISTERS[1:], 1):
        stored = "t0" if register == "sp" else register
        restored = "t1" if register == "sp" else register
        if f"sd\t{stored}, {8 * index:#x}(sp)" not in trap or f"ld\t{restored}, {8 * index:#x}(sp)" not in resume:
            raise ValueError(f"Missing linked x{index} context transfer in {image.name}")
    for instruction, code in (("csrr\tt0, mepc", trap), ("csrw\tmepc, t0", resume), ("mret", resume)):
        if instruction not in code:
            raise ValueError(f"Missing linked resume instruction {instruction}")
    if (("li\ts0, 0x0" in resume) != (policy == 2)
            or ("ld\tt1, 0x10(t2)" in resume) != (policy == 3)):
        raise ValueError(f"Invalid register-restore control in {image.name}")
    user_bytes = image.with_suffix(".user")
    execute(args.objcopy, "-O", "binary", "-j", ".user", image, user_bytes)
    return {"elf_sha256": sha256(image.read_bytes()).hexdigest(), "kernel_text_bytes": loads[0][2],
            "user_code_sha256": sha256(user_bytes.read_bytes()).hexdigest()}


def execute(*arguments):
    command = list(map(str, arguments))
    output = subprocess.run(command, capture_output=True, text=True, timeout=30)
    if output.returncode or output.stderr:
        raise ValueError(f"Command failed {command}: {output.returncode}, {output.stderr!r}")
    return output.stdout


def replay(args):
    profiles = [(name, policy, workload, reference(workload, round_robin=policy == 0))
                for name, policy in (("round_robin", 0), ("run_to_completion", 1)) for workload in WORKLOADS]
    profiles += [(name, policy, (3, 3), expected) for name, policy, expected in (
        ("clobber_saved_register", 2, "ABS"), ("restore_wrong_stack", 3, "ABK"),
        ("leave_ecall_pc_unchanged", 4, "ABP"),
    )]
    records = {}
    with TemporaryDirectory(prefix="llmlang-rv64-scheduler-") as temporary:
        work = Path(temporary)
        source = (HERE / "boot.s").read_text(encoding="utf-8")
        for name, policy, (work_a, work_b), expected in profiles:
            identity = f"{name}_{work_a}_{work_b}"
            asm = work / f"{identity}.s"
            asm.write_text(f".set POLICY, {policy}\n.set WORK_A, {work_a}\n.set WORK_B, {work_b}\n" + source,
                           encoding="utf-8")
            obj, image = asm.with_suffix(".o"), asm.with_suffix(".elf")
            execute(args.mc, "-triple", "riscv64-unknown-none-elf", "-mattr=+zicsr,+zifencei",
                    "-filetype=obj", asm, "-o", obj)
            execute(args.lld, "--no-relax", "-T", HERE / "layout.ld", "-o", image, obj)
            linked = linked_metadata(args, image, policy)
            actual = execute(args.qemu, "-machine", "virt", "-cpu", "rv64", "-m", "64M", "-smp", "1",
                             "-bios", "none", "-nodefaults", "-display", "none", "-monitor", "none",
                             "-serial", "stdio", "-kernel", image)
            if actual != expected:
                raise ValueError(f"Unexpected trace for {identity}: {actual!r}, expected {expected!r}")
            records[identity] = {**linked, "yield_budgets": [work_a, work_b], "uart": actual}
            if policy in (0, 1):
                records[identity]["maximum_intervening_peer_yields"] = interleaving_wait(actual)
    if len({record["user_code_sha256"] for record in records.values()}) != 1:
        raise ValueError("The worker code differs between profiles")
    return {"schema": "llmlang-rt38-rv64-cooperative-scheduler-v1", "machine": "virt", "cpu": "rv64", "harts": 1,
            "tools": {name: execute(getattr(args, name), "--version").splitlines()[0].strip()
                      for name in ("mc", "lld", "objdump", "qemu")},
            "input_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                             for name in ("boot.s", "layout.ld", "run.py")},
            "images": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, command in {
        "mc": "llvm-mc-19", "lld": "ld.lld-19", "readelf": "llvm-readelf-19", "nm": "llvm-nm-19",
        "objcopy": "llvm-objcopy-19", "objdump": "llvm-objdump-19", "qemu": "qemu-system-riscv64",
    }.items():
        parser.add_argument(f"--{name}", default=command)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(replay(args), indent=2) + "\n", encoding="utf-8")
