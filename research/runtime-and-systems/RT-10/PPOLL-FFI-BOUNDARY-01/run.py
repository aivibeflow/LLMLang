#!/usr/bin/env python3
"""Bind portable ppoll semantics to separate libc and target syscall adapters."""

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
    "libc expired timeout=retained stale-errno=E2BIG mask=restored",
    "libc ready event=POLLIN delivered=L mask=restored",
    "libc invalid-timeout result=EINVAL mask=restored",
    "syscall expired timeout=zero stale-errno=E2BIG mask=restored",
    "syscall ready event=POLLIN delivered=L mask=restored",
    "syscall invalid-timeout result=EINVAL mask=restored",
    "syscall libc-mask-size=128 kernel-mask-size=8 result=EINVAL",
]


def experiment(work, args):
    assert os.uname().machine == "x86_64"
    archive = Path(subprocess.check_output([args.cc, "-print-file-name=libc.a"],
                                           text=True).strip()).resolve()
    spec, musl, _ = LIBC["musl_specs"](args.musl_root.resolve(), work)
    profiles = {"glibc": (archive, ()), "musl": (musl, (f"-specs={spec}",))}
    rows = {}
    for (libc, (expected_archive, options)), level in product(profiles.items(), ("-O0", "-O2")):
        binary = work / f"probe-{libc}-{level[1:]}"
        report = subprocess.run(
            [args.cc, *options, "-std=c17", "-Wall", "-Wextra", "-Werror", "-static", "-Wl,-t",
             level, str(HERE / "probe.c"), "-o", str(binary)],
            cwd=work, check=True, capture_output=True, text=True,
        )
        chosen = {Path(line).resolve() for line in report.stdout.splitlines() if line.endswith("/libc.a")}
        assert chosen == {expected_archive.resolve()}
        run = subprocess.run([str(binary)], cwd=work, check=True, capture_output=True, text=True, timeout=20)
        assert not run.stderr and run.stdout.splitlines() == EXPECTED * 5
        rows[f"{libc}/{level}"] = {"native_observations": len(run.stdout.splitlines()),
                                  "libc_artifact": LIBC["digest"](expected_archive)}
    return {"format": "ppoll-ffi-boundary-01", "target": "linux-x86-64", "rows": rows,
            "observed_contract": EXPECTED, "kernel": os.uname().release}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--musl-root", required=True, type=Path)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-ppoll-ffi-") as work:
        evidence = experiment(Path(work), args)
    text = json.dumps(evidence, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
