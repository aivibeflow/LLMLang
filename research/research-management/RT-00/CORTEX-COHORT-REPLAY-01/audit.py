"""Replay tracked Cortex-M3 and separate embedded model evidence ledgers."""

import argparse
from collections import Counter
from hashlib import file_digest
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory

REVISION = "9a18919e11b22f47be0a83e0795569c61bb10228"
TARGET = Path("research/runtime-and-systems/RT-37")
LEAN = "+leanprover/lean4:v4.36.0"
CLANG_GUEST = ("startup-retention", "nested-stack", "nvic-clear")
RUST_GUEST = ("stack", "volatile", "timer", "closure", "allocator")
COMPOSITION = ("COMPOSED-DEVICE-BOUNDARY-01", "RESOURCE-AND-DEADLINE-01")


def sha(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def compare(ledgers):
    startup = ledgers["startup-retention"]["profiles"]
    assert len({entry["uart"] for entry in startup.values()}) == 4
    sections = [tuple(entry["sections"].items()) for entry in startup.values()]
    assert all(section == sections[0] for section in sections)

    nested = ledgers["nested-stack"]["profiles"]
    during = nested["unmask_inside_handler"]
    after = nested["unmask_in_thread"]
    assert during["trace"] == after["trace"]
    assert (during["peak_frame_bytes"], after["peak_frame_bytes"]) == (64, 32)

    pending = ledgers["nvic-clear"]["results"]
    for name, entry in pending.items():
        for row in entry["records"]:
            start = row["before_clear_alias"]
            mask = row["target_mask"]
            assert start == row["before_set_alias"]
            written = {
                "clear_selected_bit": mask,
                "read_and_not_then_write_clear": start & ~mask,
                "read_or_then_write_clear": start | mask,
                "write_selected_bit_to_set_alias": mask,
            }[name]
            expected = start | written if name.endswith("set_alias") else start & ~written
            assert row["after_pending"] == expected

    volatile = ledgers["volatile"]["images"]
    plain = volatile["llvm-plain-O0"]
    assert (plain["optimized_llvm_ir_word_loads"], len(plain["linked_word_loads"]), plain["uart"]) == (2, 1, "B11!")
    for name in ("llvm-volatile-O0", "llvm-volatile-O2", "rust-volatile-O2"):
        assert len(volatile[name]["linked_word_loads"]) == 2 and volatile[name]["uart"] == "B10!"

    isr = ledgers["isr-effects"]["images"]
    isr_outcomes = dict(Counter(row["linked_graph"] for row in isr.values()))
    assert isr_outcomes == {"ACCEPTED": 2, "REJECTED": 3, "UNKNOWN": 2}

    allocator = ledgers["allocator"]
    for route in ("llvm", "rust"):
        fixed = allocator["images"][f"{route}-fixed"]
        bump = allocator["images"][f"{route}-bump"]
        assert fixed["named"]["small_packing"]["accepted"] == 64 // 16
        assert bump["named"]["small_packing"]["accepted"] == 64 // 4

    dma = ledgers["dma-lease"]["kernel_replay"]
    device = ledgers[COMPOSITION[0]]
    deadlines = ledgers[COMPOSITION[1]]["logical_periodic_deadlines"]
    assert 2 * dma["phases"] * dma["events"] == dma["observations"]
    assert sum(device["outcomes"].values()) == 2304
    return {
        "startup_control_uart_streams": len(startup), "nested_stack_profiles": len(nested),
        "pending_bit_observations": sum(len(row["records"]) for row in pending.values()),
        "linked_isr_outcomes": isr_outcomes, "volatile_builds": len(volatile),
        "fixed_and_cursor_requests": len(allocator["images"]) * allocator["requests_per_image"],
        "dma_logical_transitions": dma["observations"],
        "device_admission_inputs": sum(device["outcomes"].values()), "abstract_deadline_checks": deadlines,
    }


def run(args, work):
    archive = work / "research.tar"
    root = work / "tree"
    root.mkdir()
    with archive.open("wb") as stream:
        subprocess.run(["git", "archive", REVISION, "research"], stdout=stream, check=True, timeout=45)
    with tarfile.open(archive) as tracked:
        tracked.extractall(root, filter="data")
    base = root / TARGET
    env = dict(os.environ, LC_ALL="C", PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")

    checked = {}
    ledgers = {}
    cohort = (*CLANG_GUEST, *RUST_GUEST, "isr-effects", "dma-lease", *COMPOSITION)
    for label in cohort:
        component = label if label in ("dma-lease", *COMPOSITION) else f"cortex-m3-{label}"
        directory = base / component
        stdout_ledger = label in (*CLANG_GUEST, *COMPOSITION)
        runner = directory / ("check.py" if label in COMPOSITION else "run.py")
        archived = directory / ("evidence.json" if stdout_ledger else "results.json")
        out = work / f"{label}.json"
        command = [sys.executable, str(runner)]
        invocation = [str(runner.relative_to(root))]
        if label in CLANG_GUEST:
            command += ["--clang", str(args.clang)]
            invocation += ["--clang", "<pinned-clang>"]
        if label in (*CLANG_GUEST, *RUST_GUEST):
            command += ["--qemu", str(args.qemu)]
            invocation += ["--qemu", "<pinned-qemu>"]
        if not stdout_ledger:
            command += ["--output", str(out)]
            invocation += ["--output", "<scratch>"]
        rerun = subprocess.run(command, cwd=root, env=env, capture_output=True, check=True, timeout=120)
        actual = rerun.stdout if stdout_ledger else out.read_bytes()
        if actual != archived.read_bytes():
            raise ValueError(f"Archived ledger differs: {component}")
        ledgers[label] = json.loads(actual)
        files = {str(path.relative_to(root)): sha(path) for path in sorted(directory.iterdir())
                 if path.is_file() and path != archived}
        checked[label] = {"ledger": str(archived.relative_to(root)), "sha256": sha(archived),
                          "invocation": invocation, "local_files_sha256": files}

    tools = {"clang": args.clang, "qemu": args.qemu}
    for name in ("llvm-mc-19", "llvm-objdump-19", "llvm-readelf-19", "llvm-nm-19", "llvm-objcopy-19",
                 "llc-19", "opt-19", "ld.lld-19", "readelf", "rustc", "lean"):
        path = shutil.which(name, path=env["PATH"])
        if path is None:
            raise ValueError(f"Missing tool: {name}")
        tools[name] = Path(path)
    records = {}
    for name, path in tools.items():
        prefix = [path, LEAN] if name == "lean" else [path]
        banner = subprocess.check_output([*prefix, "--version"], env=env, text=True, timeout=20).splitlines()[0]
        executable = path
        if name == "lean":
            libdir = subprocess.check_output([*prefix, "--print-libdir"], env=env, text=True).strip()
            executable = Path(libdir).parents[1] / "bin/lean"
        elif name == "rustc":
            sysroot = subprocess.check_output([*prefix, "--print", "sysroot"], env=env, text=True).strip()
            executable = Path(sysroot) / "bin/rustc"
        records[name] = {"banner": banner, "tool_sha256": sha(executable), "entry_sha256": sha(path)}
    return {
        "commit": REVISION, "python": sys.version.split()[0], "python_executable_sha256": sha(Path(sys.executable)),
        "host": {"machine": platform.machine(), "kernel": platform.release()},
        "tools": records, "fixtures": checked, "independent_observations": compare(ledgers),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", type=Path, required=True)
    parser.add_argument("--qemu", type=Path, required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    args.clang = args.clang.resolve(strict=True)
    args.qemu = args.qemu.resolve(strict=True)
    with TemporaryDirectory(prefix="llmlang-cortex-cohort-") as directory:
        result = run(args, Path(directory))
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
