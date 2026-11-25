"""Build controlled LLVM bitcode producers and independently audit LLD consumers."""

import argparse
import ctypes
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
VERSIONS = ("19", "22", "23")


def call(args, cwd=None, *, checked=True):
    return subprocess.run(
        args, cwd=cwd, env={**os.environ, "LC_ALL": "C", "TZ": "UTC"},
        capture_output=True, text=True, check=checked, timeout=45,
    )


def digest(blob):
    return sha256(blob).hexdigest()


def digest_file(path):
    return digest(path.read_bytes())


def emit(clang, source, work, altered=False):
    name = source.removesuffix(".c") + ("-altered" if altered else "")
    base = [
        clang, "--target=x86_64-unknown-linux-gnu", "-fPIC", "-ffreestanding",
        "-fno-ident", "-O2", "-emit-llvm",
    ]
    if altered:
        base.append("-DALTER_SEMANTICS")
    bitcode = work / f"{name}.bc"
    readable = work / f"{name}.ll"
    call([*base, "-c", source, "-o", bitcode], work)
    call([*base, "-S", source, "-o", readable], work)
    ir = readable.read_text(encoding="utf-8")
    attributes = {
        "nocapture": "nocapture" in ir,
        "captures_none": "captures(none)" in ir,
        "noundef": "noundef" in ir,
    }
    assert bitcode.read_bytes().startswith(b"BC\xc0\xde")
    return bitcode, {
        "bitcode_sha256": digest_file(bitcode), "textual_ir_sha256": digest_file(readable),
        "ir_argument_attributes": attributes,
    }


def check(artifact, profile, inputs):
    library = ctypes.CDLL(str(artifact))
    transform = library.transform
    transform.restype = ctypes.c_uint32
    if profile == "pointer":
        transform.argtypes = [ctypes.POINTER(ctypes.c_uint32)]
        actual = [transform(ctypes.byref(ctypes.c_uint32(value))) for value in inputs]
    else:
        transform.argtypes = [ctypes.c_uint32]
        actual = [transform(value) for value in inputs]
    expected = [((value ^ 0x5a5a5a5a) + 1) % 2**32 for value in inputs]
    packed = b"".join(value.to_bytes(4, "little") for value in actual)
    return {
        "calls": len(actual), "mismatches": sum(a != b for a, b in zip(actual, expected)),
        "native_trace_sha256": digest(packed),
    }


def link(linker, bitcode, profile, inputs, out):
    result = call([
        linker, "-shared", "-z", "defs", "--lto-O2", bitcode, "-o", out,
    ], checked=False)
    if result.returncode:
        assert not out.exists(), result.stderr
        first = result.stderr.splitlines()[0]
        cause = re.sub(r"\s+\(Producer:.*$", "", first.split(": error: ", 1)[-1])
        cause = cause.replace(str(bitcode), bitcode.name)
        return {"status": "link-refused", "diagnostic": cause}
    metadata = call(["readelf", "-dW", out]).stdout
    assert "(NEEDED)" not in metadata
    observed = check(out, profile, inputs)
    return {
        "status": "tested" if not observed["mismatches"] else "native-contract-refused",
        "elf_sha256": digest_file(out),
        **observed,
    }


def collect(args, temporary):
    tools = {
        label: {
            role: {
                "version": call([getattr(args, role + label), "--version"]).stdout.splitlines()[0],
                "binary_sha256": digest_file(getattr(args, role + label)),
            }
            for role in ("clang", "lld")
        }
        for label in VERSIONS
    }
    inputs = [*range(256), 0x5a5a5a5a, 0xa5a5a5a5, 0x7fffffff, 0x80000000, 0xffffffff]
    matrix = {}
    records = {}
    for source in ("value", "pointer"):
        producers = {}
        for version in VERSIONS:
            work = temporary / f"{source}-{version}"
            work.mkdir()
            owner = HERE / f"{source}.c"
            local = work / owner.name
            local.write_bytes(owner.read_bytes())
            producers[version] = emit(getattr(args, "clang" + version), owner.name, work)
        records[source] = {label: manifest for label, (_, manifest) in producers.items()}
        grid = {}
        for producer, consumer in product(VERSIONS, repeat=2):
            key = f"{producer}->{consumer}"
            bitcode, receipt = producers[producer]
            artifact = temporary / f"{source}-{producer}-to-{consumer}.so"
            grid[key] = {
                **link(getattr(args, "lld" + consumer), bitcode, source, inputs, artifact),
                "profile_sha256": digest(json.dumps([
                    tools[producer]["clang"], tools[consumer]["lld"], receipt["bitcode_sha256"],
                    source, "x86_64-unknown-linux-gnu", "-shared -z defs --lto-O2",
                ], sort_keys=True).encode("utf-8")),
            }
        matrix[source] = grid
        assert all(grid[f"{label}->{label}"]["status"] == "tested" for label in VERSIONS)

    compatibility_controls = {}
    for label in ("22", "23"):
        assert records["pointer"][label]["ir_argument_attributes"]["captures_none"]
        refusal = matrix["pointer"][f"{label}->19"]
        assert refusal["status"] == "link-refused" and "Unknown attribute kind" in refusal["diagnostic"]
        directory = temporary / f"pointer-{label}"
        source = (directory / "pointer.ll").read_text(encoding="utf-8")
        neutral = directory / "pointer-without-capture.ll"
        neutral.write_text(source.replace("captures(none) ", ""), encoding="utf-8")
        assert neutral.read_text(encoding="utf-8") != source
        bitcode = directory / "pointer-without-capture.bc"
        clang = getattr(args, "clang" + label)
        call([clang, "-x", "ir", "-emit-llvm", "-c", neutral, "-o", bitcode], directory)
        observed = link(args.lld19, bitcode, "pointer", inputs, directory / "pointer-loaded.so")
        assert observed["status"] == "tested"
        compatibility_controls[label] = {"bitcode_sha256": digest_file(bitcode), **observed}

    control_root = temporary / "control"
    control_root.mkdir()
    (control_root / "value.c").write_bytes((HERE / "value.c").read_bytes())
    altered, manifest = emit(args.clang19, "value.c", control_root, altered=True)
    control = link(args.lld19, altered, "value", inputs, control_root / "altered.so")
    assert control["status"] == "native-contract-refused" and control["mismatches"] == len(inputs)
    return {
        "toolchain": tools, "input_count_per_link": len(inputs), "producer_receipts": records,
        "links": matrix, "removed_capture_attribute_controls": compatibility_controls,
        "matching_symbol_drift_control": {**control, **manifest},
        "source_files": {
            name: digest_file(HERE / name) for name in ("run.py", "value.c", "pointer.c")
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for major, tool in product(VERSIONS, ("clang", "lld")):
        parser.add_argument(f"--{tool}{major}", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt13-llvm-bitcode-") as directory:
        evidence = collect(args, Path(directory))
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
