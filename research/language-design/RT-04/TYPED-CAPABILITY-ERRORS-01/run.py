#!/usr/bin/env python3
"""Check native capability attenuation and precise residual failure observation."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
SCOPES = tuple(product(range(8), range(3), range(3), range(3)))
DRIVER = """use cap::*;
fn main() {
    for scope in 0..8 {
        for input in 0..3 {
            for audit_mode in 0..3 {
                for write_mode in 0..3 {
                    let mut events = Vec::new();
                    let result = observe_fixture(scope, input, audit_mode, write_mode, &mut events);
                    println!("{scope} {input} {audit_mode} {write_mode}|{result:?}|{}", events.join(","));
                }
            }
        }
    }
}
"""
NEGATIVE = {
    "substitute-reader-for-writer": (
        "use cap::*; pub fn invalid(permit: Read<'_>) {"
        "let _ = write(permit, false, &mut Vec::new()); } fn main() {}", "E0308",
    ),
    "no-amplification-method": (
        "use cap::*; pub fn invalid(permit: Read<'_>) {"
        "let _ = permit.writer(); } fn main() {}", "E0599",
    ),
    "private-permit-constructor": (
        "pub fn invalid(a: &cap::Authority) { let _ = cap::Read(a); } fn main() {}", "E0603",
    ),
    "no-public-authority-constructor": (
        "fn main() { let _ = cap::Authority::from_fixture_mask(7); }", "E0624",
    ),
    "resume-after-unhandled-error": (
        "use cap::*; pub fn invalid(permit: Read<'_>) {"
        "match read(permit,0,&mut Vec::new()) {"
        "Ok(x) => println!(\"{x}\"), Err(ReadError::Missing) => {} } } fn main() {}", "E0004",
    ),
}


def oracle(mask, input_mode, audit_mode, write_mode):
    events = []
    if (mask & 1) == 0:
        return "Err(DeniedRead)", events
    events.append("read")
    if input_mode != 0:
        return ("Ok(None)" if input_mode == 1 else "Err(Busy)"), events
    for name, mode, bit in (("Audit", audit_mode, 2), ("Write", write_mode, 4)):
        if mode:
            if not mask & bit:
                return f"Err(Denied{name})", events
            events.append(name.lower())
            if mode == 2:
                return f"Err({name}Failure)", events
    return "Ok(Some(7))", events


def build(root, rustc, level):
    flags = ["--edition=2021", "-Dwarnings", "-C", f"opt-level={level}",
             "--remap-path-prefix", f"{root}=/fixture"]
    (root / "cap.rs").write_bytes((HERE / "cap.rs").read_bytes())
    subprocess.run([rustc, *flags, "--crate-type=rlib", "cap.rs", "-o", "libcap.rlib"],
                   cwd=root, check=True, capture_output=True)
    (root / "main.rs").write_text(DRIVER, encoding="utf-8")
    link = ["--extern", "cap=libcap.rlib"]
    subprocess.run([rustc, *flags, *link, "main.rs", "-o", "app"], cwd=root, check=True, capture_output=True)
    seen = subprocess.check_output(["./app"], cwd=root, text=True)
    occurrences = Counter()
    traces = []
    for scope, line in zip(SCOPES, seen.splitlines(), strict=True):
        request, result, events = line.split("|")
        assert tuple(map(int, request.split())) == scope
        ordered = events.split(",") if events else []
        assert (result, ordered) == oracle(*scope)
        occurrences[result] += 1
        if result in {"Err(DeniedWrite)", "Err(AuditFailure)"} and "audit" in ordered:
            traces.append({"scope": scope, "result": result, "events": ordered})
    refusals = {}
    for name, (source, code) in NEGATIVE.items():
        path = root / (name + ".rs")
        path.write_text(source, encoding="utf-8")
        refused = subprocess.run([rustc, *flags, *link, path.name, "-o", "invalid"],
                                 cwd=root, check=False, capture_output=True, text=True)
        assert refused.returncode != 0 and code in refused.stderr, (name, refused.stderr)
        refusals[name] = code
    assert len(traces) > 0
    return {
        "runtime_cells": len(SCOPES), "dispositions": dict(occurrences),
        "audit_before_error": len(traces), "example": traces[0],
        "native_digest": sha256(seen.encode()).hexdigest(), "compile_refusals": refusals,
    }


def experiment(root):
    rustc = os.environ.get("RUSTC", "rustc")
    measured = {}
    for level in (0, 2):
        work = root / str(level)
        work.mkdir()
        measured[level] = build(work, rustc, level)
    assert measured[0] == measured[2]
    return {"format": "typed-capability-errors-01", "outcomes": measured,
            "rust": subprocess.check_output([rustc, "--version"], text=True).strip()}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-typed-capability-") as work:
        evidence = experiment(Path(work))
    content = json.dumps(evidence, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(content, encoding="utf-8")
    else:
        print(content, end="")
