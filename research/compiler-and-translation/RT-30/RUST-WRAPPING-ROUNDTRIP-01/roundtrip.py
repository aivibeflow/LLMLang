"""Validate restricted Rust wrapping import and re-export in four compiler profiles."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CORPUS = HERE.parents[1] / "RT-13" / "GENERATED-GO-INTEGERS-01"
sys.path.insert(0, str(CORPUS))
from run import FIXTURE, reference, source, vectors
from integer_fixture import WRAPPING, compile_source
from llvm_integer_probe import _STATUS


METHODS = {name: name.replace("wrap_", "wrapping_") for name in WRAPPING}


def invoke(tool, args, directory, *, payload=None, check=True, cargo_rustc=None):
    environment = {**os.environ, "LC_ALL": "C"}
    if cargo_rustc:
        environment["RUSTC"] = cargo_rustc
    result = subprocess.run([tool, *map(str, args)], cwd=directory, input=payload,
                            capture_output=True, check=check, timeout=90, env=environment)
    return result


def original(index, term):
    template = (HERE / "original.rs.in").read_text(encoding="utf-8")
    for key, value in {"FUNCTION": f"original{index}", "METHOD": METHODS[term.operation],
                       "LEFT": term.operands[0], "RIGHT": term.operands[1]}.items():
        template = template.replace(f"@{key}@", value)
    return template


def emit(index, term):
    left, right = term.operands
    return f"""pub fn exported{index}(
    a: u32, b: u32, enabled: u32, emit: &mut dyn FnMut(u32), out: &mut u32
) -> u32 {{
    emit(a);
    let mut value = b;
    if enabled != 0 {{
        value = {left}.{METHODS[term.operation]}({right});
    }}
    emit(value);
    *out = value;
    0
}}
"""


def recognize(importer, directory, text):
    source_file = directory / "input.rs"
    source_file.write_text(text, encoding="utf-8")
    verdict = invoke(importer, (source_file,), directory).stdout.decode().split()
    match verdict:
        case ["accepted", operation, left, right]:
            return "accepted", compile_source(source(operation, left, right))
        case [refused]:
            return refused, None
        case _:
            raise ValueError(verdict)


def negative(importer, directory, wrapping):
    clean = original(0, wrapping)
    cases = {
        "invalid-syntax": (clean.replace("enabled != 0", "enabled ! 0"), "parse-error"),
        "multiple-items": (clean + "\nfn extra() {}\n", "unsupported-inventory"),
        "file-attribute": ("#![allow(dead_code)]\n" + clean, "unsupported-inventory"),
        "function-attribute": (clean.replace("pub fn", "#[inline]\npub fn"), "unsupported-shape"),
        "ordinary-add": (clean.replace("a.wrapping_add(b)", "a + b"), "unsupported-shape"),
        "checked-add": (clean.replace("a.wrapping_add(b)", "a.checked_add(b).unwrap()"), "unsupported-shape"),
        "saturating-add": (clean.replace("a.wrapping_add(b)", "a.saturating_add(b)"), "unsupported-shape"),
        "changed-condition": (clean.replace("enabled != 0", "enabled == 1"), "unsupported-shape"),
        "changed-event": (clean.replace("emit(a);", "emit(b);"), "unsupported-shape"),
        "changed-store-order": (clean.replace("emit(value); *out=value;", "*out=value; emit(value);"),
                                "unsupported-shape"),
    }
    results = {}
    for name, (candidate, status) in cases.items():
        verdict, result = recognize(importer, directory, candidate)
        if (verdict, result) != (status, None):
            raise AssertionError((name, status, verdict, result))
        results[name] = verdict
    return results


def native_build(rustc, directory, source_file, route, opt, checks):
    artifact = directory / f"{route}-O{opt}-{checks}"
    invoke(rustc, ("--edition=2021", "--crate-name", "bounded_probe", "-D", "warnings",
                   f"-Copt-level={opt}", f"-Coverflow-checks={checks}", "-Cdebuginfo=0",
                   "--remap-path-prefix", f"{directory}=/fixture", source_file, "-o", artifact), directory)
    return artifact


def write_host(directory, route, fixtures):
    host = (HERE / "host.rs.in").read_text(encoding="utf-8")
    entries = ", ".join(f"{route}{index}" for index in range(len(fixtures)))
    path = directory / f"{route}.rs"
    path.write_text("#![forbid(unsafe_code)]\n" + "\n".join(fixtures) +
                    host.replace("@ENTRIES@", entries), encoding="utf-8")
    return path


def observations(artifact, directory, request, expected):
    response = invoke(artifact, (), directory, payload=request).stdout
    if len(response) != 20 * len(expected):
        raise ValueError("Invalid response length")
    counts = Counter()
    for index, ((status, slot, count, first, second), wanted) in enumerate(
        zip(struct.iter_unpack("<5I", response), expected, strict=True)
    ):
        if count not in (1, 2):
            raise ValueError((index, count))
        actual = (_STATUS[status], slot, (first, second)[:count])
        if actual != wanted:
            raise AssertionError((artifact.name, index, wanted, actual))
        counts[actual[0]] += 1
    return {"records": len(expected), "statuses": dict(sorted(counts.items())),
            "trace_sha256": sha256(response).hexdigest(),
            "binary_sha256": sha256(artifact.read_bytes()).hexdigest()}


def bare_add(rustc, directory):
    facts = {}
    for checks in ("yes", "no"):
        artifact = native_build(rustc, directory, HERE / "bare-add.rs", "bare", 0, checks)
        observed = invoke(artifact, (), directory, check=False)
        if checks == "yes":
            if observed.returncode != 101 or b"attempt to add with overflow" not in observed.stderr:
                raise AssertionError(observed)
            facts[checks] = "overflow-panic"
        else:
            if observed.returncode or observed.stdout != b"0\n":
                raise AssertionError(observed)
            facts[checks] = "returned-zero"
    return facts


def verify(args, directory):
    toolchain = invoke(args.rustc, ("-vV",), directory).stdout.decode().splitlines()
    if not {"release: 1.85.1", "host: x86_64-unknown-linux-gnu"} <= set(toolchain):
        raise ValueError(("unsupported evidence profile", toolchain))
    target = directory / "parser-target"
    invoke(args.cargo, ("build", "--offline", "--locked", "--manifest-path", HERE / "Cargo.toml",
                        "--target-dir", target), directory, cargo_rustc=args.rustc)
    importer = target / "debug" / "bounded-wrapping-import"

    programs = tuple(compile_source(source(op, left, right)) for op, (left, right)
                     in product(WRAPPING, product("ab", repeat=2)))
    incoming = tuple(original(index, term) for index, term in enumerate(programs))
    imported = tuple(recognize(importer, directory, text) for text in incoming)
    if imported != tuple(("accepted", term) for term in programs):
        raise AssertionError("Original Rust import changed the operation")
    outgoing = tuple(emit(index, term) for index, (_, term) in enumerate(imported))
    if tuple(recognize(importer, directory, text) for text in outgoing) != imported:
        raise AssertionError("Rust reimport changed the operation")

    indexed = tuple(product(range(len(programs)), vectors()))
    wanted = tuple(reference(programs[index], vector) for index, vector in indexed)
    request = b"".join(struct.pack("<4I", index, *vector) for index, vector in indexed)
    results = {}
    for route, fixtures in (("original", incoming), ("exported", outgoing)):
        host = write_host(directory, route, fixtures)
        for opt, checks in product((0, 3), ("yes", "no")):
            binary = native_build(args.rustc, directory, host, route, opt, checks)
            results[f"{route}-O{opt}-checks-{checks}"] = observations(binary, directory, request, wanted)

    paths = ("Cargo.toml", "Cargo.lock", "src/main.rs", "host.rs.in", "original.rs.in", "bare-add.rs", "roundtrip.py")
    inputs = [*(HERE / name for name in paths), CORPUS / "run.py", FIXTURE / "integer_fixture.py",
              FIXTURE / "llvm_integer_probe.py"]
    return {
        "rustc": toolchain,
        "original_distinct_programs": len(programs),
        "successful_reimports": len(outgoing),
        "negative": negative(importer, directory, programs[1]),
        "bare_add_native": bare_add(args.rustc, directory),
        "native_profiles": results,
        "source_sha256": {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
                          for path in inputs},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rustc", default="rustc")
    parser.add_argument("--cargo", default="cargo")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-rust-roundtrip-") as temp:
        print(json.dumps(verify(args, Path(temp)), indent=2))


if __name__ == "__main__":
    main()
