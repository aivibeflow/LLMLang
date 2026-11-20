"""Run the RT-04 native probes and preserve machine-readable execution evidence."""

import argparse
import ctypes
from ctypes.util import find_library
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
EXPECTED_C_SQLITE_VERSION = "3.46.1"
EXPECTED_C_SQLITE_SOURCE_ID = (
    "2024-08-13 09:16:08 c9c2ab54ba1f5f46360f1b4f35d849cd3f080e6fc2b6c60e91b16c63f69aalt1"
)
EXPECTED_RUSTC_VERSION = "1.85.1"
HISTORICAL_PYTHON_SQLITE_VERSION = "3.53.1"


def _decode(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def runtime_metadata():
    metadata = {
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "commit": os.environ.get("GITHUB_SHA"),
        "python_sqlite_version": None,
        "python_sqlite_historical_baseline": HISTORICAL_PYTHON_SQLITE_VERSION,
        "python_sqlite_matches_historical_baseline": False,
        "durable_python_sqlite_version": None,
        "durable_python_sqlite_source_id": None,
        "durable_python_sqlite_matches_historical_baseline": False,
        "durable_python_sqlite_library": os.environ.get("LLMLANG_PYTHON_SQLITE_LIBRARY"),
        "c_sqlite_library": os.environ.get("LLMLANG_SQLITE_LIBRARY") or find_library("sqlite3"),
        "c_sqlite_version": None,
        "c_sqlite_source_id": None,
        "rustc_version": None,
        "rustc_verbose": None,
    }
    try:
        import sqlite3
        metadata["python_sqlite_version"] = sqlite3.sqlite_version
        metadata["python_sqlite_matches_historical_baseline"] = (
            sqlite3.sqlite_version == HISTORICAL_PYTHON_SQLITE_VERSION
        )
    except Exception as exc:
        metadata["python_sqlite_error"] = repr(exc)

    durable_env = os.environ.copy()
    durable_library = durable_env.get("LLMLANG_PYTHON_SQLITE_LIBRARY")
    if durable_library:
        durable_lib_dir = str(Path(durable_library).resolve().parent)
        durable_env["LD_LIBRARY_PATH"] = os.pathsep.join(
            item for item in (durable_lib_dir, durable_env.get("LD_LIBRARY_PATH", "")) if item
        )
    try:
        probe = subprocess.run(
            [
                sys.executable, "-c",
                "import sqlite3; c=sqlite3.connect(':memory:'); "
                "print(sqlite3.sqlite_version); print(c.execute('select sqlite_source_id()').fetchone()[0])",
            ],
            cwd=ROOT, env=durable_env, capture_output=True, text=True, timeout=15, check=True,
        )
        version, source_id = probe.stdout.strip().splitlines()
        metadata["durable_python_sqlite_version"] = version
        metadata["durable_python_sqlite_source_id"] = source_id
        metadata["durable_python_sqlite_matches_historical_baseline"] = (
            version == HISTORICAL_PYTHON_SQLITE_VERSION
        )
    except Exception as exc:
        metadata["durable_python_sqlite_error"] = repr(exc)

    library_name = metadata["c_sqlite_library"]
    if library_name:
        try:
            library = ctypes.CDLL(library_name)
            library.sqlite3_libversion.restype = ctypes.c_char_p
            library.sqlite3_sourceid.restype = ctypes.c_char_p
            metadata["c_sqlite_version"] = _decode(library.sqlite3_libversion())
            metadata["c_sqlite_source_id"] = _decode(library.sqlite3_sourceid())
        except Exception as exc:
            metadata["c_sqlite_error"] = repr(exc)

    try:
        version = subprocess.run(
            ["rustc", "--version"], cwd=ROOT, capture_output=True, text=True, timeout=15, check=True
        )
        verbose = subprocess.run(
            ["rustc", "-vV"], cwd=ROOT, capture_output=True, text=True, timeout=15, check=True
        )
        metadata["rustc_version"] = version.stdout.strip()
        metadata["rustc_verbose"] = verbose.stdout.strip()
    except Exception as exc:
        metadata["rustc_error"] = repr(exc)
    return metadata


def commands_for(suite):
    python = sys.executable
    prefix = [python, "-B"]
    sqlite = [
        ("sqlite-cleanup-contracts", prefix + ["research/PROTOTYPES/RT-04-01/sqlite_cleanup_probe.py"]),
        ("sqlite-recovery-matrix", prefix + ["research/PROTOTYPES/RT-04-01/sqlite_cleanup_probe.py", "--recovery-matrix"]),
        ("sqlite-snapshot-freshness", prefix + ["research/PROTOTYPES/RT-04-01/sqlite_cleanup_probe.py", "--snapshot-freshness"]),
        ("sqlite-close-call-boundary", prefix + ["research/PROTOTYPES/RT-04-01/sqlite_close_call_probe.py"]),
        ("sqlite-close-interleavings", prefix + ["research/PROTOTYPES/RT-04-01/sqlite_close_interleavings_probe.py"]),
        ("sqlite-close-reentry-and-coverage", prefix + ["research/PROTOTYPES/RT-04-01/sqlite_close_reentry_probe.py"]),
        ("sqlite-backup-roles", prefix + ["research/PROTOTYPES/RT-04-01/sqlite_backup_roles_probe.py"]),
        ("sqlite-backup-outcomes", prefix + ["research/PROTOTYPES/RT-04-01/sqlite_backup_outcomes_probe.py"]),
    ]
    durable = [
        ("sqlite-durable-receipts", prefix + ["research/PROTOTYPES/RT-04-01/sqlite_durable_receipts_probe.py"]),
    ]
    rust = [
        ("generated-rust-owned-results", prefix + [
            "research/PROTOTYPES/RT-04-01/rt04_rust_owned_probe.py", "--rustc", "rustc"
        ]),
    ]
    if suite == "sqlite":
        return sqlite
    if suite == "durable":
        return durable
    if suite == "rust":
        return rust
    return sqlite + durable + rust


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("all", "sqlite", "durable", "rust"), default="all")
    parser.add_argument("--output-dir", default="artifacts/rt04-native-reproduction")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()

    output = (ROOT / args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    metadata = runtime_metadata()
    print("Native runtime metadata:")
    print(json.dumps({
        "commit": metadata.get("commit"),
        "python": sys.version.split()[0],
        "python_sqlite_version": metadata.get("python_sqlite_version"),
        "python_sqlite_matches_historical_baseline": metadata.get("python_sqlite_matches_historical_baseline"),
        "durable_python_sqlite_version": metadata.get("durable_python_sqlite_version"),
        "durable_python_sqlite_source_id": metadata.get("durable_python_sqlite_source_id"),
        "durable_python_sqlite_matches_historical_baseline": metadata.get("durable_python_sqlite_matches_historical_baseline"),
        "durable_python_sqlite_library": metadata.get("durable_python_sqlite_library"),
        "c_sqlite_library": metadata.get("c_sqlite_library"),
        "c_sqlite_version": metadata.get("c_sqlite_version"),
        "c_sqlite_source_id": metadata.get("c_sqlite_source_id"),
        "platform": metadata.get("platform"),
        "rustc_version": metadata.get("rustc_version"),
        "rustc_verbose": metadata.get("rustc_verbose"),
    }, indent=2), flush=True)
    summary = {
        "schema_version": 1,
        "suite": args.suite,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "repository_commit": metadata.get("commit"),
        "runtime": metadata,
        "expected": {
            "c_sqlite_version": EXPECTED_C_SQLITE_VERSION,
            "c_sqlite_source_id": EXPECTED_C_SQLITE_SOURCE_ID,
            "rustc_version": EXPECTED_RUSTC_VERSION,
            "historical_python_sqlite_version": HISTORICAL_PYTHON_SQLITE_VERSION,
        },
        "preflight_errors": [],
        "commands": [],
    }

    run_sqlite = args.suite in ("all", "sqlite")
    c_sqlite_ok = (
        metadata.get("c_sqlite_version") == EXPECTED_C_SQLITE_VERSION
        and metadata.get("c_sqlite_source_id") == EXPECTED_C_SQLITE_SOURCE_ID
    )
    if run_sqlite and not c_sqlite_ok:
        summary["preflight_errors"].append(
            "C SQLite must match the Scenario 120–128 baseline exactly: "
            f"version={metadata.get('c_sqlite_version')!r}, "
            f"source_id={metadata.get('c_sqlite_source_id')!r}"
        )

    run_durable = args.suite in ("all", "durable")
    durable_sqlite_ok = (
        metadata.get("durable_python_sqlite_version") == HISTORICAL_PYTHON_SQLITE_VERSION
    )
    if run_durable and not durable_sqlite_ok:
        summary["preflight_errors"].append(
            "Scenario 130 requires Python sqlite3 "
            f"{HISTORICAL_PYTHON_SQLITE_VERSION}; observed "
            f"{metadata.get('durable_python_sqlite_version')!r}"
        )

    if args.suite in ("all", "rust"):
        rustc = metadata.get("rustc_version") or ""
        if not rustc.startswith(f"rustc {EXPECTED_RUSTC_VERSION} "):
            summary["preflight_errors"].append(
                f"Rust runner requires rustc {EXPECTED_RUSTC_VERSION}; observed {rustc!r}"
            )

    selected = commands_for(args.suite)
    for index, (name, command) in enumerate(selected, start=1):
        if name.startswith("sqlite-") and name not in ("sqlite-durable-receipts",) and not c_sqlite_ok:
            summary["commands"].append({
                "name": name, "command": command, "status": "skipped",
                "reason": "C SQLite preflight did not match the pinned Scenario 120–128 baseline",
            })
            (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
            continue
        if name == "sqlite-durable-receipts" and not durable_sqlite_ok:
            summary["commands"].append({
                "name": name, "command": command, "status": "skipped",
                "reason": "Python sqlite3 preflight did not match the Scenario 130 baseline",
            })
            (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\\n", encoding="utf-8")
            continue

        stdout_path = output / f"{index:02d}-{name}.stdout.txt"
        stderr_path = output / f"{index:02d}-{name}.stderr.txt"
        item = {
            "name": name,
            "command": shlex.join(command),
            "status": "completed",
            "timeout_seconds": args.timeout_seconds,
        }
        try:
            command_env = None
            if name == "sqlite-durable-receipts":
                command_env = os.environ.copy()
                durable_library = command_env.get("LLMLANG_PYTHON_SQLITE_LIBRARY")
                if durable_library:
                    durable_lib_dir = str(Path(durable_library).resolve().parent)
                    command_env["LD_LIBRARY_PATH"] = os.pathsep.join(
                        item for item in (durable_lib_dir, command_env.get("LD_LIBRARY_PATH", "")) if item
                    )
            result = subprocess.run(
                command, cwd=ROOT, env=command_env, capture_output=True, text=True,
                timeout=args.timeout_seconds, check=False,
            )
            stdout, stderr = result.stdout, result.stderr
            item["exit_code"] = result.returncode
            item["status"] = "passed" if result.returncode == 0 else "failed"
        except subprocess.TimeoutExpired as exc:
            stdout = _decode(exc.stdout or "")
            stderr = _decode(exc.stderr or "")
            item["status"] = "timed_out"
            item["timeout_seconds"] = args.timeout_seconds
        except Exception as exc:
            stdout, stderr = "", repr(exc)
            item["status"] = "failed_to_start"
            item["error"] = repr(exc)

        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        item["stdout_file"] = stdout_path.name
        item["stderr_file"] = stderr_path.name
        summary["commands"].append(item)
        summary["finished_at"] = datetime.now(timezone.utc).isoformat()
        (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"[{item['status']}] {name}", flush=True)
        if stdout.strip():
            print(f"--- {name} stdout ---", flush=True)
            print(stdout.rstrip(), flush=True)
        if stderr.strip():
            print(f"--- {name} stderr ---", flush=True)
            print(stderr.rstrip(), flush=True)

    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    summary["passed"] = sum(item["status"] == "passed" for item in summary["commands"])
    summary["failed"] = sum(item["status"] in ("failed", "failed_to_start", "timed_out") for item in summary["commands"])
    summary["skipped"] = sum(item["status"] == "skipped" for item in summary["commands"])
    summary["success"] = not summary["preflight_errors"] and summary["failed"] == 0 and summary["skipped"] == 0
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": summary["success"],
        "passed": summary["passed"],
        "failed": summary["failed"],
        "skipped": summary["skipped"],
        "preflight_errors": summary["preflight_errors"],
        "summary": str(output / "summary.json"),
    }, indent=2))
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
