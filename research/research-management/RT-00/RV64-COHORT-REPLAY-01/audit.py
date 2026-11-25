"""Replay exact archived RV64 fixtures and check cross-ledger scope invariants."""

import argparse
from collections import deque
from fractions import Fraction
from hashlib import file_digest
import json
from math import factorial
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory

REVISION = "ccb5f3102dc8e8e64c1042582955d8319d32005b"
RT38 = Path("research/runtime-and-systems/RT-38")
PROFILE = "RV64-FREESTANDING-PROFILE-01"
HAL = "RV64-HAL-QEMU-01"
TIMER = "RV64-TIMER-PREEMPTION-01"
IPC = "RV64-PREEMPTIVE-IPC-01"
LIVE = "RV64-LIVE-FRAME-IPC-01"
SCOPED = "SCOPED-SMP-DMA-REUSE-01"
GUESTS = (HAL, TIMER, IPC, LIVE)
COHORT = (PROFILE, *GUESTS, SCOPED)


def hash_file(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def schedule(policy, credits):
    """Generate only task credit and retirement events for the admitted timer cases."""
    queue = deque(zip("ab", credits, strict=True))
    events = []
    while queue:
        task, credit = queue.popleft()
        if credit == 0:
            events.append(task)
            continue
        events.append(task.upper())
        if policy == "round_robin":
            queue.append((task, credit - 1))
        else:
            queue.appendleft((task, credit - 1))
    return "".join(events) + "!"


def version(tool, env):
    result = subprocess.run([tool, "--version"], env=env, text=True, capture_output=True,
                            timeout=10, check=True)
    return result.stdout.splitlines()[0]


def check_observations(ledgers, qemu_hash):
    scope = ledgers[PROFILE]["scope_controls"]
    for domain in ("rv64-physical", "rv64-qemu-smp"):
        assert scope[f"{domain}/isolated-ipc"] == "outside-profile"
    assert scope["rv64-qemu-single-hart/source-to-linked-refinement"] == "outside-profile"

    assert {ledgers[name]["qemu_sha256"] for name in GUESTS} == {qemu_hash}
    hal = ledgers[HAL]["profiles"]
    base = hal["assembly"]
    for route in ("llvm-O0", "llvm-O2", "llvm-O3"):
        assert hal[route]["leaf_words"] == base["leaf_words"]
        assert hal[route]["load_regions"] == base["load_regions"]
        assert hal[route]["uart"] == base["uart"]
    assert base["leaf_words"]["translation_barrier"][0] == "12000073"
    assert hal["wrong-fence"]["leaf_words"]["translation_barrier"] == base["leaf_words"]["memory_barrier"]
    assert hal["wrong-stack"]["uart"] != base["uart"] != hal["wrong-fence"]["uart"]

    timer = ledgers[TIMER]["profiles"]
    compatible = [route for route in timer if route.startswith(("keep_current", "round_robin"))]
    for route in compatible:
        policy = route.split("-")[0]
        assert schedule(policy, timer[route]["timer_credits"]) == timer[route]["uart"]
    assert set(timer) - set(compatible) == {"saved_register_fault-3-3", "wrong_continuation-3-3"}
    assert [timer[key]["uart"][-1] for key in sorted(set(timer) - set(compatible))] == ["S", "T"]

    ipc = ledgers[IPC]["observations"]
    for route in ("deliver", "revoke"):
        symbols = ipc[route]["page_table_and_stack_symbols"]
        assert int(symbols["root_a"], 16) != int(symbols["root_b"], 16)
        assert int(symbols["stack_a_top"], 16) <= int(symbols["stack_b"], 16)
    assert {entry["uart"][-1] for entry in ipc.values()} == {"!", "T", "K"}
    assert "R" in ipc["revoke"]["uart"] and "R" in ipc["accept_stale_generation"]["uart"]

    live = ledgers[LIVE]["profiles"]
    linked_fences = {route: row["translation_fences_in_transaction"] for route, row in live.items()}
    for row in live.values():
        old = int(row["old_frame"], 16)
        new = int(row["replacement_frame"], 16)
        assert old % 4096 == new % 4096 == 0 and old != new
    assert linked_fences == {
        "dirty_publication": 2, "publish_old_frame": 2,
        "sanitized_replacement": 2, "wake_before_mapping": 1,
    }
    assert {name: row["uart"][-1] for name, row in live.items()} == {
        "dirty_publication": "M", "publish_old_frame": "O",
        "sanitized_replacement": "!", "wake_before_mapping": "F",
    }

    logical = ledgers[SCOPED]
    matrix = logical["matrix"]
    # With exact CPU receipts, each inactive device channel can take any of six variants.
    assert matrix["rows"] == 4 * 6**4 and matrix["allowed"] == 6**2 + 1
    assert matrix["device_rows_allowed"] == 1
    # Four of six variants name the same frame but only one is an exact acknowledgment.
    assert matrix["frame_only_false_accepts"] == 4**2 * 6**2 + 4**4 - matrix["allowed"]
    assert matrix["ignoring_one_channel_false_accepts"] == {
        "local-hart": 5 * 6**2 + 5, "remote-hart": 5 * 6**2 + 5,
        "dma-drain": 5, "device-visibility": 5,
    }
    histories = logical["ordered_histories"]
    histories_per_policy = factorial(7) // 2
    assert histories["schedules"] == 4 * histories_per_policy
    # When the remote epoch matches, detach comes first among required events.
    # The first reuse can sit in any k+2 positions before the final valid reuse.
    probability = sum(Fraction(factorial(k) * (k + 2), factorial(k + 3) // 2) for k in (2, 4))
    assert histories["reassigned"] == histories_per_policy * probability
    assert histories["blocked"] + histories["reassigned"] == histories["reuse_requests"]
    assert len(logical["lean_audit"]) == 7 and len(ledgers[TIMER]["proof_audit"]) == 4
    return {
        "runnable_guest_profiles": sum(len(ledgers[name].get("profiles", ledgers[name].get("observations")))
                                       for name in GUESTS),
        "archived_profile_images": ledgers[PROFILE]["distinct_rv64_elf_digests"],
        "independent_scheduler_traces": len(compatible),
        "linked_frame_controls": len(live),
        "conditional_receipt_rows": matrix["rows"], "conditional_histories": histories["schedules"],
        "lean_theorems": len(logical["lean_audit"]) + len(ledgers[TIMER]["proof_audit"]),
        "physical_and_smp_transfer": "outside-qemu-evidence",
    }


def audit(args, work):
    tree = work / "tree"
    tree.mkdir()
    archive = work / "research.tar"
    with archive.open("wb") as handle:
        subprocess.run(["git", "archive", REVISION, "research"], stdout=handle, timeout=30, check=True)
    with tarfile.open(archive) as package:
        package.extractall(tree, filter="data")
    base = tree / RT38

    env = dict(os.environ, LC_ALL="C", PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
    inputs = {}
    ledgers = {}
    for name in COHORT:
        runner = base / name / "run.py"
        observed = work / f"{name}.json"
        command = [sys.executable, str(runner), "--output", str(observed)]
        logical_command = [str(RT38 / name / "run.py"), "--output", "<scratch>"]
        if name in GUESTS:
            command += ["--qemu", str(args.qemu), "--qemu-data", str(args.qemu_data)]
            logical_command += ["--qemu", "<qemu>", "--qemu-data", "<qemu-data>"]
        subprocess.run(command, env=env, cwd=tree, timeout=90, check=True)
        expected = runner.with_name("evidence.json")
        if observed.read_bytes() != expected.read_bytes():
            raise ValueError(f"Ledger mismatch: {name} ({hash_file(observed)}, {hash_file(expected)})")
        ledger = json.loads(observed.read_bytes())
        ledgers[name] = ledger
        key = next((name for name in ("source_sha256", "source_pins", "sources") if name in ledger), None)
        sources = {}
        if key:
            source_root = runner.parent if name == SCOPED else base
            for path, digest in ledger[key].items():
                if hash_file(source_root / path) != digest:
                    raise ValueError(f"Source hash mismatch: {path}")
                sources[str((source_root / path).relative_to(tree))] = digest
        inputs[name] = {
            "ledger_sha256": hash_file(expected), "runner_sha256": hash_file(runner),
            "source_sha256": sources, "command": logical_command,
        }

    tools = {"qemu": args.qemu}
    for tool in ("llvm-mc-19", "opt-19", "llc-19", "ld.lld-19", "llvm-objdump-19", "llvm-readelf-19",
                 "llvm-nm-19", "llvm-objcopy-19", "lean"):
        selected = shutil.which(tool)
        if selected is None:
            raise ValueError(f"Required tool not on PATH: {tool}")
        tools[tool] = Path(selected)
    return {
        "revision": REVISION, "python": sys.version.split()[0],
        "python_sha256": hash_file(Path(sys.executable)),
        "host": {"machine": platform.machine(), "kernel": platform.release(),
                 "libc": subprocess.check_output(["getconf", "GNU_LIBC_VERSION"], text=True).strip()},
        "guest": {"machine": "virt", "cpu": "rv64", "memory_mib": 64, "harts": 1,
                  "firmware": "none", "instruction_clock": "shift=0,align=off,sleep=off"},
        "reproduced": inputs,
        "tools": {name: {"sha256": hash_file(path), "version": version(path, env)}
                  for name, path in tools.items()},
        "observation_checks": check_observations(ledgers, hash_file(args.qemu)),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qemu", type=Path, required=True)
    parser.add_argument("--qemu-data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.qemu = args.qemu.resolve(strict=True)
    args.qemu_data = args.qemu_data.resolve(strict=True)
    with TemporaryDirectory(prefix="rv64-cohort-") as work:
        result = audit(args, Path(work))
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
