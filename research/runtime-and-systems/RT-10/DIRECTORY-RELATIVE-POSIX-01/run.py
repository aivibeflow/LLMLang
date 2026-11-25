#!/usr/bin/env python3
"""Compare descriptor-relative operations with ambient POSIX cwd resolution."""

import argparse
from itertools import product
import json
import os
from pathlib import Path
import runpy
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
LIBC = runpy.run_path(str(HERE.parent / "POSIX-CROSS-LIBC-01/run.py"))
EXPECTED = [
    "original A A A", "peer-cwd-changed B A A", "peer-cwd-restored A A A",
    "rename-and-replace C A A 1 1", "errors EBADF ENOTDIR ENOENT", "remaining-owner A EBADF",
]


def experiment(work, args):
    compiler = args.cc
    standard = Path(subprocess.check_output([compiler, "-print-file-name=libc.a"],
                                           text=True).strip()).resolve()
    spec, musl, _ = LIBC["musl_specs"](args.musl_root.resolve(), work)
    profiles = {"glibc": (standard, ()), "musl": (musl, (f"-specs={spec}",))}
    archive_identity = LIBC["digest"]
    assert archive_identity(standard) != archive_identity(musl)
    rows = {}
    for (name, (archive, flags)), opt in product(profiles.items(), ("-O0", "-O2")):
        exe = work / f"probe-{name}-{opt[1:]}"
        report = subprocess.run(
            [compiler, *flags, "-std=c17", "-Wall", "-Wextra", "-Werror", "-static", "-pthread",
             "-Wl,-t", opt, str(HERE / "probe.c"), "-o", str(exe)],
            cwd=work, check=True, capture_output=True, text=True,
        )
        selected = {Path(line).resolve() for line in report.stdout.splitlines() if line.endswith("/libc.a")}
        assert selected == {archive.resolve()}
        for run in range(1, 4):
            directory = work / f"{name}-{opt[1:]}-{run}"
            directory.mkdir()
            probe = subprocess.run([str(exe)], cwd=directory, check=True, text=True,
                                   capture_output=True, timeout=30)
            assert not probe.stderr and probe.stdout.splitlines() == EXPECTED
        rows[f"{name}/{opt}"] = {"archive": archive_identity(archive), "observed_fields": EXPECTED, "runs": 3}
    return {
        "format": "directory-relative-posix-01", "kernel": os.uname().release,
        "observations": 6 * 3 * len(rows), "rows": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--musl-root", required=True, type=Path)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-directory-relative-") as directory:
        evidence = experiment(Path(directory), args)
    text = json.dumps(evidence, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
