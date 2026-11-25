"""Check output-type relationships with separately compiled native Rust clients."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE = "56fbb55f31994ef9a519368131e6b62bff646bdc"
INPUTS = tuple(range(256))
NARROW = [(value + 1) % 256 for value in INPUTS]
WIDE = [value + 256 for value in INPUTS]


def native_body(expression):
    return f"""
fn main() {{
    for input in 0u8..=255 {{
        let value = {{ {expression} }};
        println!("{{value}}");
    }}
}}
"""


def cases():
    # Each control compiles against a previously built provider library.
    yield "self-inferred", "self_keyed", "", native_body("Provider.decode(input)"), WIDE
    yield "self-anywidth-wrong", "self_keyed", "", """
fn main() {
    let _: u8 = Provider.decode(1);
}
""", "E0308"
    yield "self-erased-unbound", "self_keyed", "", """
fn main() {
    let _: &dyn Decode = &Provider;
}
""", "E0191"
    yield "self-erased-bound", "self_keyed", "", native_body("""
let provider: &dyn Decode<Output = u16> = &Provider;
provider.decode(input)
"""), WIDE
    yield "caller-narrow", "caller_chosen", "", native_body("""
let value: u8 = Provider.decode(input);
value
"""), NARROW
    yield "caller-wide", "caller_chosen", "", native_body("""
let value: u16 = Provider.decode(input);
value
"""), WIDE
    yield "caller-ambiguous", "caller_chosen", "", """
fn main() {
    let _ = Provider.decode(1);
}
""", "E0283"
    yield "caller-selected-erased", "caller_chosen", "", native_body("""
let provider: &dyn Decode<u8> = &Provider;
provider.decode(input)
"""), NARROW
    yield "input-inferred-narrow", "input_keyed", "", native_body("Provider.decode(input)"), NARROW
    yield "input-inferred-wide", "input_keyed", "", native_body("Provider.decode(u16::from(input))"), WIDE
    yield "input-cannot-select-conflicting-output", "input_keyed", "", """
fn main() {
    let _: u16 = Provider.decode(1u8);
}
""", "E0308"
    yield "input-erased-unbound", "input_keyed", "", """
fn main() {
    let _: &dyn Decode<u8> = &Provider;
}
""", "E0191"
    yield "input-erased-bound", "input_keyed", "", native_body("""
let provider: &dyn Decode<u8, Output = u8> = &Provider;
provider.decode(input)
"""), NARROW
    yield "input-erased-wrong-association", "input_keyed", "", """
fn main() {
    let _: &dyn Decode<u8, Output = u16> = &Provider;
}
""", "E0271"
    yield "input-generalized-output", "input_keyed", """
fn call<D: Decode<I>, I>(d: &D, input: I) -> D::Output {
    d.decode(input)
}
""", native_body("call(&Provider, input)"), NARROW


def compile_case(rustc, source, binary, library):
    result = subprocess.run(
        [rustc, "--edition=2021", "--error-format=json", "--crate-name", "client",
         "--extern", f"fixture={library}", str(source), "-o", str(binary)],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode == 0:
        return []
    codes = []
    for row in result.stderr.splitlines():
        message = json.loads(row)
        if message.get("level") == "error" and message.get("code"):
            codes.append(message["code"]["code"])
    assert codes, result.stderr
    return codes


def exercise(rustc, directory):
    libraries = {}
    for interface in ("self_keyed", "caller_chosen", "input_keyed"):
        location = directory / interface
        location.mkdir()
        library = location / "libfixture.rlib"
        subprocess.run(
            [rustc, "--edition=2021", "--crate-type=rlib", "--crate-name", "fixture",
             str(HERE / f"{interface}.rs"), "-o", str(library)],
            check=True, capture_output=True, timeout=30,
        )
        libraries[interface] = library
    results = {}
    for name, interface, helper, body, expected in cases():
        source = directory / f"{name}.rs"
        text = "use fixture::*;\n" + helper + body
        source.write_text(text, encoding="utf-8")
        binary = directory / name
        codes = compile_case(rustc, source, binary, libraries[interface])
        row = {"interface": interface, "source": text, "error_codes": codes}
        if isinstance(expected, str):
            assert codes == [expected], (name, codes, expected)
        else:
            assert not codes, (name, codes)
            raw = subprocess.check_output([binary], text=True, timeout=10)
            values = [int(value) for value in raw.splitlines()]
            assert values == expected, name
            row["values"] = values
        results[name] = row
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rustc", required=True, type=Path)
    args = parser.parse_args()
    rustc = args.rustc.resolve()
    version = subprocess.check_output([rustc, "-vV"], text=True, timeout=10).splitlines()
    assert "commit-hash: 4eb161250e340c8f48f66e2b929ef4a5bed7c181" in version
    with tempfile.TemporaryDirectory(prefix="llmlang-generic-output-") as temporary:
        results = exercise(rustc, Path(temporary))
    print(json.dumps({
        "baseline": BASELINE, "rustc": version, "python": platform.python_version(),
        "host_os": os.uname().sysname, "host_arch": os.uname().machine,
        "input_range_inclusive": [min(INPUTS), max(INPUTS)],
        "source_sha256": {
            name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
            for name in ("run.py", "self_keyed.rs", "caller_chosen.rs", "input_keyed.rs")
        },
        "cases": results,
    }, indent=2))


if __name__ == "__main__":
    main()
