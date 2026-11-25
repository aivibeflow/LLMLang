#!/usr/bin/env python3
"""Check observable POSIX pipe claims and separate Linux extension evidence."""

import argparse
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
import os
from pathlib import Path
import runpy
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
LIBC = runpy.run_path(str(HERE.parent / "POSIX-CROSS-LIBC-01/run.py"))
PROOF = HERE.parent / "POSIX-WRITEV-TYPED-PROGRESS-01/Output.lean"
NATIVE = [
    "linux-shrink busy-when-occupied empty-capacity=4096 unchanged-pipe-buf=4096",
    "atomic-small blocked-request=4096 committed=0",
    "large-nonblocking request=8192 committed=4096",
    "atomic-small empty-request=4096 committed=4096",
]


@dataclass(frozen=True)
class Claim:
    profile: str
    kind: str
    feature: str
    operation: str
    view: str
    schema: int = 1


def fingerprint(raw):
    return sha256(raw).hexdigest()


def receipt(claim, evidence):
    return {"claim": asdict(claim), "evidence": fingerprint(evidence)}


def exact_id(record):
    return fingerprint(json.dumps(record, sort_keys=True, separators=(",", ":")).encode())


def gate(claim, provided, trusted):
    if provided is None:
        return "unknown"
    if provided["claim"] != asdict(claim):
        return "scope-mismatch"
    if exact_id(provided) not in trusted:
        return "unverified"
    return claim.kind


def check_claims(profiles, header_probes, native, raw_proof):
    glibc_native = {"rows": native["glibc/-O2"]}
    musl_native = {"rows": native["musl/-O2"]}
    def encode(data):
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()

    glibc = "linux-x86-64/glibc:" + profiles["glibc"]
    musl = "linux-x86-64/musl:" + profiles["musl"]
    observed = Claim(glibc, "scoped-observation", "bounded-pipe", "write", "atomic-nonblocking")
    extension = Claim(glibc, "scoped-observation", "linux-capacity", "fcntl", "capacity-only")
    header = Claim(glibc, "header-only", "linux-capacity", "fcntl", "macro-declaration")
    theorem = Claim("lean-prefix-model/1", "formal-model", "ordered-vector", "resume", "list-prefix")
    musl_observed = replace(observed, profile=musl)
    records = {
        "write": receipt(observed, encode(glibc_native)),
        "musl-write": receipt(musl_observed, encode(musl_native)),
        "extension": receipt(extension, encode(glibc_native)),
        "header": receipt(header, encode(header_probes["glibc/GNU"])),
        "proof": receipt(theorem, PROOF.read_bytes() + b"\0" + raw_proof),
    }
    authorized = {exact_id(row) for row in records.values()}
    results = {}
    for name, claim, supplied, expected in (
        ("exact scoped write", observed, records["write"], "scoped-observation"),
        ("same observation on different libc", musl_observed, records["write"], "scope-mismatch"),
        ("verified native observation for musl", musl_observed, records["musl-write"], "scoped-observation"),
        ("exact scoped Linux extension", extension, records["extension"], "scoped-observation"),
        ("header is header evidence", header, records["header"], "header-only"),
        ("declared extension promoted to runtime", extension, records["header"], "scope-mismatch"),
        ("extension promoted to POSIX", replace(extension, profile="POSIX-general"), records["extension"], "scope-mismatch"),
        ("pipe bytes used for another operation", replace(observed, operation="writev"), records["write"], "scope-mismatch"),
        ("general atomicity outside fixture size", replace(observed, view="all-sizes"), records["write"], "scope-mismatch"),
        ("logical prefix theorem exact", theorem, records["proof"], "formal-model"),
        ("prefix theorem promoted to kernel verification", replace(theorem, profile=glibc), records["proof"], "scope-mismatch"),
        ("scoped native receipts cannot prove generic POSIX", replace(observed, kind="formal-model"), records["write"], "scope-mismatch"),
        ("missing receipt", observed, None, "unknown"),
        ("altered evidence hash", observed, records["write"] | {"evidence": "0" * 64}, "unverified"),
        ("different receipt schema", replace(theorem, schema=2), records["proof"], "scope-mismatch"),
    ):
        result = gate(claim, supplied, authorized)
        assert result == expected
        results[name] = result
    return results


def experiment(work, args):
    std = Path(subprocess.check_output([args.cc, "-print-file-name=libc.a"], text=True).strip()).resolve()
    spec, musl, _ = LIBC["musl_specs"](args.musl_root.resolve(), work)
    profiles = {"glibc": (std, ()), "musl": (musl, (f"-specs={spec}",))}
    native = {}
    headers = {}
    archives = {key: LIBC["digest"](path) for key, (path, _) in profiles.items()}
    assert archives["glibc"] != archives["musl"]
    for name, (archive, flags) in profiles.items():
        for feature, args_flag in (("POSIX", "-D_POSIX_C_SOURCE=200809L"), ("GNU", "-D_GNU_SOURCE")):
            macros = subprocess.check_output(
                [args.cc, *flags, args_flag, "-dM", "-E", "-x", "c", "-"],
                cwd=work, input="#include <fcntl.h>\n#include <unistd.h>\n", text=True,
            )
            headers[f"{name}/{feature}"] = {
                key: any(row.startswith(f"#define {key} ") for row in macros.splitlines())
                for key in ("F_GETPIPE_SZ", "F_SETPIPE_SZ", "_PC_PIPE_BUF")
            }
            assert headers[f"{name}/{feature}"]["_PC_PIPE_BUF"]
        for level in ("-O0", "-O2"):
            binary = work / f"probe-{name}-{level[1:]}"
            report = subprocess.run(
                [args.cc, *flags, "-std=c17", "-Wall", "-Wextra", "-Werror", "-static", "-Wl,-t",
                 level, str(HERE / "probe.c"), "-o", str(binary)],
                cwd=work, check=True, text=True, capture_output=True,
            )
            selected = {Path(row).resolve() for row in report.stdout.splitlines() if row.endswith("/libc.a")}
            assert selected == {archive.resolve()}
            native[f"{name}/{level}"] = subprocess.check_output([str(binary)], cwd=work,
                                                                 text=True, timeout=20).splitlines()
            assert native[f"{name}/{level}"] == NATIVE
    proof = subprocess.run([args.lean, "-DwarningAsError=true", str(PROOF)],
                           cwd=work, check=True, capture_output=True)
    assert proof.stdout.splitlines()[0] == b"'exact_prefix_resume' does not depend on any axioms"
    assert b"sorryAx" not in proof.stdout
    return {
        "format": "pipe-conformance-scope-01", "kernel": os.uname().release, "runtime_profiles": archives,
        "native": native, "headers": headers, "evidence_scope_controls": check_claims(archives, headers, native, proof.stdout),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--musl-root", required=True, type=Path)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--lean", default="lean")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-pipe-conformance-") as place:
        result = experiment(Path(place), args)
    content = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
