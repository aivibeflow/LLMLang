#!/usr/bin/env python3
"""Compare foreign owned-return policies using real Linux stdio and locks."""

import argparse
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
OPT_LEVELS = ("0", "3")
DIMENSIONS = ("early", "wants_value", "broken_pipe", "foreign_duplicate", "same_inode")


def expected_trace(early, wants_value, broken_pipe, duplicate, same_inode):
    early_transfer = early and wants_value
    staged_transfer = not early and wants_value and not broken_pipe
    forwarded = early_transfer or staged_transfer
    blocked = same_inode and (forwarded or duplicate)

    return [
        *(["transfer"] if early_transfer else []),
        "fclose_epipe" if broken_pipe else "fclose_ok",
        "stream_fd_closed",
        *([] if broken_pipe else ["flushed_byte"]),
        *(["transfer"] if staged_transfer else []),
        *(["owner_fd_open"] if forwarded else ["provider_close", "owner_fd_closed"]),
        *(["duplicate_fd_open"] if duplicate else []),
        "second_refused" if blocked else "second_started",
        *(["caller_close"] if forwarded else []),
        *(["duplicate_close"] if duplicate else []),
        *(["second_retry_started"] if blocked else []),
    ]


def command_output(arguments):
    command = subprocess.run(arguments, text=True, capture_output=True, check=True, timeout=30)
    if command.stderr:
        raise ValueError(f"Unexpected diagnostics from {arguments[0]}: {command.stderr}")
    return command.stdout.strip()


def run(compiler):
    if platform.system() != "Linux":
        raise ValueError("This experiment requires Linux flock and stdio semantics")

    source = HERE / "owned_cleanup.c"
    domain = tuple(product((False, True), repeat=len(DIMENSIONS)))
    records = []
    with TemporaryDirectory(prefix="llmlang-foreign-owned-") as scratch:
        directory = Path(scratch)
        target, alias, disjoint = [directory / name for name in ("target", "alias", "disjoint")]
        target.touch()
        disjoint.touch()
        alias.hardlink_to(target)
        if not target.samefile(alias) or target.samefile(disjoint):
            raise ValueError("Fixture alias identities do not match the intended inodes")
        filesystem = command_output(["stat", "-f", "-c", "%T", str(directory)])

        binaries = [directory / f"probe-O{opt}" for opt in OPT_LEVELS]
        for opt, binary in zip(OPT_LEVELS, binaries, strict=True):
            subprocess.run([compiler, "-std=c17", "-Wall", "-Wextra", "-Werror", f"-O{opt}",
                            str(source), "-o", str(binary)], check=True, timeout=30)

        for inputs in domain:
            early, wants, broken, duplicate, same_inode = inputs
            argv = [str(int(flag)) for flag in (early, wants, broken, duplicate)]
            comparison = alias if same_inode else disjoint
            for opt, binary in zip(OPT_LEVELS, binaries, strict=True):
                observed = command_output([str(binary), *argv, str(target), str(comparison)]).splitlines()
                if observed != expected_trace(*inputs):
                    raise ValueError(f"Unexpected O{opt} trace for {inputs}: {observed}")
            records.append({**dict(zip(DIMENSIONS, inputs, strict=True)), "events": observed})

    return {
        "schema": "llmlang-linux-foreign-owned-cleanup-v1",
        "python": sys.version,
        "compiler": command_output([compiler, "--version"]).splitlines()[0],
        "libc": command_output(["getconf", "GNU_LIBC_VERSION"]),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "filesystem": filesystem,
        "source_sha256": {
            file.name: sha256(file.read_bytes()).hexdigest() for file in (source, Path(__file__))
        },
        "optimization_levels": list(OPT_LEVELS),
        "native_trace_comparisons": len(domain) * len(OPT_LEVELS),
        "observations": records,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="cc")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    ledger = run(args.cc)
    args.output.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    print(f"{ledger['native_trace_comparisons']} native traces match the reference")
