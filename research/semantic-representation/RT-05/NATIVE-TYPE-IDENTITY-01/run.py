"""Compare compile-time type admission and the observed ABI of transparent wrappers."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
GO_DECLARATIONS = """
package probe

type Distance struct { Value uint64 }
type Mass struct { Value uint64 }
type DistanceAlias = Distance

func distance(Distance) {}
func unnamed(struct { Value uint64 }) {}
"""
GO_CASES = {
    "identical-unnamed": ("unnamed(struct { Value uint64 }{3})", True),
    "different-field-name": ("unnamed(struct { Other uint64 }{3})", False),
    "different-field-type": ("unnamed(struct { Value int64 }{3})", False),
    "different-tag": ('unnamed(struct { Value uint64 `unit:"m"` }{3})', False),
    "unnamed-to-named": ("distance(struct { Value uint64 }{3})", True),
    "named-to-unnamed": ("unnamed(Mass{3})", True),
    "different-named": ("distance(Mass{3})", False),
    "named-alias": ("distance(DistanceAlias{3})", True),
    "explicit-named-conversion": ("distance(Distance(Mass{3}))", True),
    "explicit-tagged-conversion": (
        'distance(Distance(struct { Value uint64 `unit:"m"` }{3}))', True,
    ),
}
RUST_DECLARATIONS = """
mod first {
    pub struct Record { pub value: u64 }
    pub type Alias = Record;
}
mod second {
    pub struct Record { pub value: u64 }
}
#[repr(transparent)]
struct Distance(u64);
#[repr(transparent)]
struct Mass(u64);
fn record(_: first::Record) {}
fn tuple(_: (u64, i64)) {}
fn distance(_: Distance) {}
"""
RUST_CASES = {
    "identical-tuple": ("tuple((3_u64, -7_i64));", None),
    "reversed-tuple-types": ("let reversed = (-7_i64, 3_u64); tuple(reversed);", "E0308"),
    "nominal-record-alias": ("record(first::Alias { value: 3 });", None),
    "same-shaped-second-record": ("record(second::Record { value: 3 });", "E0308"),
    "explicit-record-construction": (
        "let other = second::Record { value: 3 };\n"
        "    record(first::Record { value: other.value });", None,
    ),
    "same-abi-second-wrapper": ("distance(Mass(3));", "E0308"),
    "bare-field-to-wrapper": ("distance(3_u64);", "E0308"),
    "explicit-wrapper-construction": ("distance(Distance(Mass(3).0));", None),
}
RUST_FFI = {
    "default-layout-rejected": (False, None),
    "transparent-layout-available": (True, "#[repr(transparent)]"),
}


def invoke(argv, cwd, check=True):
    return subprocess.run(argv, cwd=cwd, check=check, capture_output=True, text=True,
                          timeout=60, env={**os.environ, "LC_ALL": "C"})


def run_go(go, work):
    rows = []
    for name, (body, accepted) in GO_CASES.items():
        (work / "probe.go").write_text(GO_DECLARATIONS + f"\nfunc test() {{ {body} }}\n")
        result = invoke([go, "tool", "compile", "probe.go"], work, check=False)
        diagnostic = result.stdout + result.stderr
        assert (result.returncode == 0) == accepted, (name, diagnostic)
        if not accepted:
            assert re.search(r"cannot use .+ as .+ value in argument to", diagnostic), diagnostic
        rows.append({"case": name, "admitted": accepted, "classification":
                     "assignable" if accepted else "assignment-rejected"})
    return rows


def run_rust(rustc, work):
    rows = []
    for name, (body, error) in RUST_CASES.items():
        source = RUST_DECLARATIONS + f"\nfn test() {{\n    {body}\n}}\n"
        (work / "probe.rs").write_text(source)
        result = invoke([rustc, "--crate-type=lib", "--emit=metadata", "probe.rs"],
                        work, check=False)
        assert result.returncode == (1 if error else 0), (name, result.stderr)
        codes = re.findall(r"^error\[(E\d+)\]", result.stderr, re.MULTILINE)
        assert codes == ([error] if error else []), (name, result.stderr)
        rows.append({"case": name, "admitted": error is None, "error_code": error})
    for name, (accepted, repr_attribute) in RUST_FFI.items():
        (work / "probe.rs").write_text(
            "#![deny(improper_ctypes_definitions)]\n"
            f"{repr_attribute or ''}\n"
            "pub struct Value(u64);\n"
            "pub extern \"C\" fn identity(value: Value) -> Value { value }\n"
        )
        result = invoke([rustc, "--crate-type=lib", "--emit=metadata", "probe.rs"],
                        work, check=False)
        assert result.returncode == (0 if accepted else 1), (name, result.stderr)
        if not accepted:
            assert "this struct has unspecified layout" in result.stderr, result.stderr
        rows.append({"case": name, "admitted": accepted, "classification":
                     "ffi-lint-accepted" if accepted else "unspecified-layout"})
    return rows


def run_abi(rustc, cc, work):
    rows = []
    for rust_opt in (0, 3):
        invoke([rustc, "--crate-type=staticlib", f"-Copt-level={rust_opt}",
                str(HERE / "abi.rs"), "-o", "libprobe.a"], work)
        for c_opt in (0, 2):
            invoke([cc, "-std=c17", "-Wall", "-Wextra", "-Werror", f"-O{c_opt}",
                    str(HERE / "abi.c"), "libprobe.a", "-ldl", "-lpthread", "-lm",
                    "-o", "abi"], work)
            size, alignment, inputs = map(int, invoke(["./abi"], work).stdout.split())
            assert inputs == 386 and size == 8
            rows.append({"rust_optimization": rust_opt, "c_optimization": c_opt,
                         "size": size, "alignment": alignment, "inputs": inputs,
                         "verified_foreign_calls": 3 * inputs})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--go", default="go")
    parser.add_argument("--rustc", default="rustc")
    parser.add_argument("--cc", default="cc")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="native-type-identity-") as directory:
        work = Path(directory)
        abi = run_abi(args.rustc, args.cc, work)
        go = run_go(args.go, work)
        rust = run_rust(args.rustc, work)
        receipt = {
            "tools": {
                "go": invoke([args.go, "version"], work).stdout.strip(),
                "rustc": invoke([args.rustc, "-vV"], work).stdout.splitlines(),
                "cc": invoke([args.cc, "--version"], work).stdout.splitlines()[0],
                "cc_target": invoke([args.cc, "-dumpmachine"], work).stdout.strip(),
            },
            "source_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                              for name in ("abi.c", "abi.rs", "run.py")},
            "go_compile": go,
            "rust_compile": rust,
            "native_abi": abi,
            "totals": {"compile_controls": len(go) + len(rust),
                       "native_calls": sum(row["verified_foreign_calls"] for row in abi)},
        }
        print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
