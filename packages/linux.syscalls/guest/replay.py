#!/usr/bin/env python3
"""Rebuild and replay the fixed privileged syscall probes in disposable guests."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from run import KERNEL_SHA256, run, source_hashes

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evidence.freeze import BOCHS_SUITE, VM_CPUS, VM_MODULES, VM_NUMA, VM_QUOTA, VM_SUITES  # noqa: E402
from guest.run_bochs import replay as replay_bochs  # noqa: E402
from package import PROVIDER, PackageError, rust_tools  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", required=True, type=Path)
    parser.add_argument("--qemu", default="qemu-system-x86_64")
    parser.add_argument("--cc", default="cc")
    parser.add_argument("--bios", type=Path, required=True)
    parser.add_argument("--firmware", type=Path)
    parser.add_argument(
        "--module-archive-root", required=True, type=Path, help="pinned guest module kernel directory",
    )
    parser.add_argument("--mke2fs", default="mke2fs")
    parser.add_argument("--bochs-root", required=True, type=Path)
    parser.add_argument("--iso-root", required=True, type=Path)
    parser.add_argument("--video-bios", required=True, type=Path)
    parser.add_argument("--output", type=Path, required=True, help="new directory for replay results")
    args = parser.parse_args()
    try:
        rust_tools()
        reports = {}
        with tempfile.TemporaryDirectory(prefix="llmlang-guest-probes-") as build:
            subprocess.run(
                [
                    "cargo", "build", "--locked", "--offline", "--release", "--examples",
                    "--manifest-path", str(PROVIDER / "Cargo.toml"), "--target-dir", build,
                ],
                env={**os.environ, "RUSTFLAGS": "-C target-feature=+crt-static"},
                check=True, timeout=180,
            )
            for suite, (example, cases) in VM_SUITES.items():
                executable = Path(build) / "release/examples" / example
                if suite == BOCHS_SUITE:
                    reports[suite] = replay_bochs(
                        args.kernel, executable, args.bochs_root, args.iso_root,
                        args.video_bios, args.cc, 180, PROVIDER,
                    )
                    continue
                report, _ = run(
                    args.kernel, KERNEL_SHA256, executable,
                    qemu=args.qemu, cc=args.cc, bios=args.bios, firmware=args.firmware,
                    cpu=VM_CPUS.get(suite), numa=suite in VM_NUMA,
                    module_root=args.module_archive_root, modules=VM_MODULES.get(suite, ()),
                    quota_image=suite in VM_QUOTA, mke2fs=args.mke2fs,
                    expected_cases=sorted({case for names in cases.values() for case in names}),
                )
                reports[suite] = report | source_hashes(PROVIDER, example)
        args.output.mkdir()
        for suite, report in reports.items():
            path = args.output / f"{suite}-evidence.json"
            path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except (OSError, PackageError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"guest replay: {error}\n")
    print(f"Replayed {len(reports)} disposable guest suites")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
