#!/usr/bin/env python3
"""Compare RV64 Sv39 frame-allocation policies with abstract ownership traces."""

import argparse
from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from make_fixture import boot, layout
from reference import RECORD_SIZE, reference_steps, sequences, violations


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "riscv-trap-isolation"
SPEC = importlib.util.spec_from_file_location("rv64_trap_isolation", BASE / "run.py")
isolation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(isolation)
execute = isolation.execute

POLICIES = {
    "zero_on_allocation": (0, "0", "EISRZZPZ!", None),
    "zero_on_release": (1, "3", "EISRZZPZ!", None),
    "dirty_publication": (2, "0", "EISRVVPZ!", {"dirty_at_publication"}),
    "lost_reservation": (3, "0", "EISRZZPZ!", {"reservation_after_return"}),
    "double_publication": (4, "0", "EISRZZPZ!", {"aliased_frame", "mapping_ownership_disagreement"}),
}


def compare(trace, name, initialization, user_trace, expected_violations):
    if not trace.startswith("B" + initialization) or not trace.endswith(user_trace):
        raise ValueError(f"Unexpected boot scrub count or U-mode probe for {name}")
    evidence = trace[2:-len(user_trace)]
    cursor = 0
    differences = 0
    scrubbed = Counter()
    errors = Counter()
    first_error = None
    targeted = []
    for commands in sequences():
        expected = reference_steps(commands, zero_on_release=name == "zero_on_release")
        for index, (command, reference) in enumerate(zip(commands, expected, strict=True)):
            observed = evidence[cursor:cursor + RECORD_SIZE]
            if len(observed) != RECORD_SIZE:
                raise ValueError(f"Truncated allocator trace for {name}")
            cursor += RECORD_SIZE
            scrubbed[observed[0]] += int(observed[8])
            differences += observed != reference
            for error in violations(observed):
                errors[error] += 1
                if first_error is None:
                    first_error = {"sequence": commands, "step_index": index, "command": command,
                                   "observed": observed,
                                   "reference": reference, "violation": error}
            if len(commands) > 3:
                targeted.append(observed)
    if cursor != len(evidence):
        raise ValueError(f"Unexpected trailing allocator observations for {name}")
    if expected_violations is None and (differences or errors):
        raise ValueError(f"Positive policy diverged for {name}: {differences}, {errors}")
    if expected_violations is not None and (not differences or set(errors) != expected_violations):
        raise ValueError(f"Negative control did not isolate {expected_violations} for {name}: {errors}")
    return {"uart_sha256": sha256(trace.encode("ascii")).hexdigest(), "user_uart": user_trace,
            "initial_scrubbed_words": int(initialization) * 512, "operations": cursor // RECORD_SIZE,
            "operation_scrubbed_words_by_status": {status: pages * 512 for status, pages in sorted(scrubbed.items())},
            "different_reference_records": differences, "violations": dict(errors),
            "first_violation": first_error, "targeted_records": targeted}


def replay(args):
    lean_axioms = execute(args.lean, HERE / "Frame.lean")
    expected_axioms = [
        "'FrameAllocator.conservation' depends on axioms: [propext, Quot.sound]",
        *[f"'FrameAllocator.{name}' does not depend on any axioms"
          for name in ("publication_requires_zero", "no_double_allocation", "both_abort_points_restore_free",
                       "unique_owner")],
    ]
    if lean_axioms.splitlines() != expected_axioms:
        raise ValueError(f"Unexpected Lean proof report: {lean_axioms!r}")
    with TemporaryDirectory(prefix="llmlang-rv64-allocator-") as temporary:
        work = Path(temporary)
        asm, linker, kernel = (work / name for name in ("boot.s", "memory.ld", "boot.o"))
        asm.write_text(boot((BASE / "boot.s").read_text(encoding="utf-8")), encoding="utf-8")
        linker.write_text(layout((BASE / "memory.ld").read_text(encoding="utf-8")), encoding="utf-8")
        execute(args.mc, "-triple", "riscv64-unknown-none-elf", "-mattr=+zicsr,+zifencei",
                "-filetype=obj", asm, "-o", kernel)
        records = {}
        for name, (policy, initialization, user_trace, expected_violations) in POLICIES.items():
            obj, image = work / f"{name}.o", work / f"{name}.elf"
            execute(args.clang, "--target=riscv64-unknown-none-elf", "-march=rv64ima_zicsr", "-mabi=lp64",
                    "-mcmodel=medany", "-mno-relax", "-ffreestanding", "-fno-builtin", "-fno-stack-protector",
                    "-fno-unwind-tables", "-fno-asynchronous-unwind-tables", "-O2", "-Wall", "-Wextra", "-Werror",
                    f"-DPOLICY={policy}", "-c", HERE / "allocator.c", "-o", obj)
            execute(args.lld, "--no-relax", "-T", linker, "-o", image, kernel, obj)
            exact = isolation.check_elf(args, image, paged=True)
            symbols = execute(args.nm, "--defined-only", image)
            if exact["loads"][-1]["file_bytes"] != 16384 or not re.search(
                    r"^0*80401000 d frames$", symbols, re.MULTILINE):
                raise ValueError(f"Frame arena layout changed for {name}")
            trace = execute(args.qemu, "-machine", "virt", "-cpu", "rv64", "-m", "64M", "-smp", "1",
                            "-bios", "none", "-nodefaults", "-display", "none", "-monitor", "none",
                            "-serial", "stdio", "-kernel", image)
            records[name] = {"elf_sha256": exact["elf_sha256"], "kernel_text_bytes": exact["loads"][0]["file_bytes"],
                             "user_code_sha256": exact["user_code_sha256"],
                             **compare(trace, name, initialization, user_trace, expected_violations)}
    if len({record["user_code_sha256"] for record in records.values()}) != 1:
        raise ValueError("U-mode bytes differ across allocator policies")
    inputs = {"base-boot.s": BASE / "boot.s", "base-memory.ld": BASE / "memory.ld", "base-run.py": BASE / "run.py"}
    inputs.update((name, HERE / name) for name in ("allocator.c", "Frame.lean", "make_fixture.py", "reference.py", "run.py"))
    return {"schema": "llmlang-rt38-rv64-frame-allocator-v1", "machine": "virt", "cpu": "rv64", "harts": 1,
            "tools": {name: execute(getattr(args, name), "--version").splitlines()[0].strip()
                      for name in ("clang", "lean", "mc", "lld", "qemu")},
            "input_sha256": {name: sha256(path.read_bytes()).hexdigest() for name, path in inputs.items()},
            "lean_axioms": lean_axioms.splitlines(), "images": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, command in {
        "clang": "clang-19", "lean": "lean", "mc": "llvm-mc-19", "lld": "ld.lld-19", "readelf": "llvm-readelf-19",
        "nm": "llvm-nm-19", "objcopy": "llvm-objcopy-19", "qemu": "qemu-system-riscv64",
    }.items():
        parser.add_argument(f"--{name}", default=command)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(replay(args), indent=2) + "\n", encoding="utf-8")
