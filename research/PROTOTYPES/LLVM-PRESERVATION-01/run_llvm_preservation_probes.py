"""Reproduce the bounded LLVM integer and byte-view preservation experiments."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
EXPECTED_PYTHON = (3, 12, 14)
EXPECTED_LLVM_VERSION = "19.1.7"
EXPECTED_LLVM_PACKAGE = "1:19.1.7-3+b1"
EXPECTED_LLVM_PACKAGE_SHA256 = "0b1b7263f4f45e261099240fdbf00fc14b42b88410fd829e041bf83ea45866cb"
EXPECTED_GCC_VERSION = "14.2.0"
EXPECTED_LD_VERSION = "2.44"


def capture(command):
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30, check=False)
    return {"command": command, "exit_code": result.returncode, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}


def runtime_metadata(args):
    opt = capture([args.opt, "--version"])
    llc = capture([args.llc, "--version"])
    cc = capture([args.cc, "--version"])
    ld = capture(["ld", "--version"])
    libc = capture(["ldd", "--version"])
    package = capture(["dpkg-query", "-W", "-f=${Version}", "llvm-19"])
    package_path = os.environ.get("LLMLANG_LLVM_DEB_PATH")
    package_sha = None
    if package_path and Path(package_path).is_file():
        package_sha = hashlib.sha256(Path(package_path).read_bytes()).hexdigest()

    metadata = {
        "commit": os.environ.get("GITHUB_SHA"),
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "libc": platform.libc_ver(),
        "opt": opt,
        "llc": llc,
        "cc": cc,
        "ld": ld,
        "libc_version": libc,
        "llvm_package_version": package,
        "llvm_package_archive": package_path,
        "llvm_package_archive_sha256": package_sha,
    }
    errors = []
    if sys.version_info[:3] != EXPECTED_PYTHON:
        errors.append(f"Python must be {EXPECTED_PYTHON}, got {sys.version_info[:3]}")
    if opt["exit_code"] or EXPECTED_LLVM_VERSION not in opt["stdout"]:
        errors.append("opt version does not match LLVM 19.1.7")
    if llc["exit_code"] or EXPECTED_LLVM_VERSION not in llc["stdout"]:
        errors.append("llc version does not match LLVM 19.1.7")
    if package["exit_code"] or package["stdout"] != EXPECTED_LLVM_PACKAGE:
        errors.append(f"llvm-19 package must be {EXPECTED_LLVM_PACKAGE}, got {package['stdout']!r}")
    if package_sha != EXPECTED_LLVM_PACKAGE_SHA256:
        errors.append(f"llvm-19 package SHA-256 mismatch: {package_sha!r}")
    if cc["exit_code"] or EXPECTED_GCC_VERSION not in cc["stdout"]:
        errors.append("C compiler does not match GCC 14.2.0")
    if ld["exit_code"] or EXPECTED_LD_VERSION not in ld["stdout"]:
        errors.append("GNU ld does not match 2.44")
    return metadata, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opt", default="/usr/bin/opt-19")
    parser.add_argument("--llc", default="/usr/bin/llc-19")
    parser.add_argument("--cc", default="/usr/bin/gcc-14")
    parser.add_argument("--output-dir", default="artifacts/llvm-preservation-reproduction")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()

    output = (ROOT / args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    metadata, preflight_errors = runtime_metadata(args)
    summary = {
        "schema_version": 1,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "repository_commit": metadata["commit"],
        "expected": {
            "python": ".".join(map(str, EXPECTED_PYTHON)),
            "llvm_version": EXPECTED_LLVM_VERSION,
            "llvm_package": EXPECTED_LLVM_PACKAGE,
            "llvm_package_sha256": EXPECTED_LLVM_PACKAGE_SHA256,
            "gcc_version": EXPECTED_GCC_VERSION,
            "gnu_ld_version": EXPECTED_LD_VERSION,
        },
        "runtime": metadata,
        "preflight_errors": preflight_errors,
        "commands": [],
    }
    print("LLVM reproduction runtime:")
    print(json.dumps(metadata, indent=2), flush=True)

    if not preflight_errors:
        commands = [
            ("llvm-integer-preservation", [
                sys.executable, "-B",
                "research/PROTOTYPES/LLVM-PRESERVATION-01/llvm_integer_probe.py",
                "--opt", args.opt, "--llc", args.llc, "--cc", args.cc,
            ]),
            ("llvm-byte-view-preservation", [
                sys.executable, "-B",
                "research/PROTOTYPES/LLVM-PRESERVATION-01/llvm_view_probe.py",
                "--opt", args.opt, "--llc", args.llc, "--cc", args.cc,
            ]),
        ]
        for index, (name, command) in enumerate(commands, start=1):
            stdout_path = output / f"{index:02d}-{name}.stdout.txt"
            stderr_path = output / f"{index:02d}-{name}.stderr.txt"
            item = {
                "name": name,
                "command": command,
                "timeout_seconds": args.timeout_seconds,
            }
            try:
                result = subprocess.run(
                    command, cwd=ROOT, capture_output=True, text=True,
                    timeout=args.timeout_seconds, check=False,
                )
                stdout, stderr = result.stdout, result.stderr
                item["exit_code"] = result.returncode
                item["status"] = "passed" if result.returncode == 0 else "failed"
            except subprocess.TimeoutExpired as exc:
                stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
                item["status"] = "timed_out"
            except Exception as exc:
                stdout, stderr = "", repr(exc)
                item["status"] = "failed_to_start"
                item["error"] = repr(exc)
            stdout_path.write_text(stdout, encoding="utf-8")
            stderr_path.write_text(stderr, encoding="utf-8")
            item["stdout_file"] = stdout_path.name
            item["stderr_file"] = stderr_path.name
            summary["commands"].append(item)
            print(f"[{item['status']}] {name}", flush=True)
            if stdout.strip():
                print(stdout.rstrip(), flush=True)
            if stderr.strip():
                print(stderr.rstrip(), flush=True)
            summary["finished_at"] = datetime.now(timezone.utc).isoformat()
            (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    summary["passed"] = sum(item["status"] == "passed" for item in summary["commands"])
    summary["failed"] = sum(item["status"] in ("failed", "failed_to_start", "timed_out") for item in summary["commands"])
    summary["success"] = not preflight_errors and summary["failed"] == 0 and summary["passed"] == 2
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": summary["success"],
        "passed": summary["passed"],
        "failed": summary["failed"],
        "preflight_errors": summary["preflight_errors"],
        "summary": str(output / "summary.json"),
    }, indent=2), flush=True)
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
