#!/usr/bin/env python3
"""Check native partial vector output against exact octet and typed progress oracles."""

import argparse
from itertools import product
import json
import os
from pathlib import Path
import runpy
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
REFERENCE = runpy.run_path(str(HERE.parent / "POSIX-CROSS-LIBC-01/run.py"))


def fingerprint(data):
    result = 0
    for value in data:
        result = (result * 257 + value) % 2**64
    return result


def observation(line):
    raw = line.split()
    naive, unit, first, resumed, total, result = map(int, raw[:6])
    control = raw[6:]
    expected = bytes((index * 73 + index // 251) % 251 + 1 for index in range(2 * unit))
    actual_good = expected if not naive else expected[:unit] + expected
    assert first == unit and resumed == (2 * unit if naive else unit) and total == len(actual_good)
    assert result == fingerprint(actual_good)
    assert control == ["EAGAIN", "zero", "EPIPE"]
    return {
        "retained_prefix": first, "resumed_bytes": resumed, "delivered_bytes": total,
        "duplicate_bytes": unit if naive else 0, "fingerprint": result,
        "requested_size": 2 * unit,
        "semantics": {"full": "would-block", "empty": "zero-request", "closed": "peer-closed"},
    }


def experiment(work, config):
    cc = config.cc
    system_archive = Path(subprocess.check_output([cc, "-print-file-name=libc.a"],
                                                 text=True).strip()).resolve()
    musl_spec, musl_archive, _ = REFERENCE["musl_specs"](config.musl_root.resolve(), work)
    profiles = {"glibc": (system_archive, ()), "musl": (musl_archive, (f"-specs={musl_spec}",))}
    assert REFERENCE["digest"](musl_archive) != REFERENCE["digest"](system_archive)
    rows = {}
    for (name, (archive, options)), use_raw, opt in product(profiles.items(), (0, 1), (0, 2)):
        key = f"{name}/{'syscall' if use_raw else 'writev'}/O{opt}"
        binary = work / key.replace("/", "-")
        cmd = [cc, *options, "-std=c17", "-Wall", "-Wextra", "-Werror", "-static", "-Wl,-t",
               f"-O{opt}", f"-DRAW={use_raw}", str(HERE / "probe.c"), "-o", str(binary)]
        report = subprocess.run(cmd, cwd=work, check=True, capture_output=True, text=True)
        picked = {Path(line).resolve() for line in report.stdout.splitlines() if line.endswith("/libc.a")}
        assert picked == {archive.resolve()}
        native = subprocess.check_output([str(binary)], cwd=work, text=True)
        first, next = native.splitlines()
        assert first.startswith("0 ") and next.startswith("1 ")
        rows[key] = {"libc_archive": REFERENCE["digest"](archive), "resume": observation(first),
                     "full_reissue": observation(next)}
    assert len(rows) == 8 and len({json.dumps(row["resume"], sort_keys=True) for row in rows.values()}) == 1
    proof = subprocess.run([config.lean, "-DwarningAsError=true", str(HERE / "Output.lean")],
                           cwd=work, text=True, capture_output=True, check=True)
    assert not proof.stderr and len(proof.stdout.splitlines()) == 2
    assert "sorryAx" not in proof.stdout
    return {"format": "posix-writev-typed-progress-01", "native": rows,
            "axiom_audit": proof.stdout.splitlines(), "machine": os.uname().machine}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--musl-root", type=Path, required=True)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--lean", default="lean")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-posix-writev-") as path:
        result = experiment(Path(path), args)
    content = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
