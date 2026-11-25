"""Reproduce the RT-12 carrier observation on Linux x86-64."""

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
FIXTURES = ("contracts.json", "contracts.S", "contracts.rc", "provider.c")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def run(*argv, cwd=None):
    return subprocess.run(
        argv, cwd=cwd, check=True, text=True, capture_output=True, timeout=30,
        env={**os.environ, "LC_ALL": "C", "TZ": "UTC"},
    ).stdout


def elf_contract(notes):
    entries = re.findall(
        r"^  LLMLANG\s+(0x[0-9a-fA-F]+).*0x4c4c4d01.*\n"
        r" +description data: ([0-9a-f ]+)$", notes, re.MULTILINE,
    )
    if not entries:
        return None
    [(size, hex_data)] = entries
    payload = bytes.fromhex(hex_data)
    assert len(payload) == int(size, 16)
    return payload


def pe_contract(report):
    if "Type: RCDATA (ID 10)" not in report:
        return None
    [size] = re.findall(r"DataSize: (\d+)", report)
    assert "Name: (ID 101)" in report and "Language: (ID 0)" in report
    rows = re.findall(r"^ +[0-9A-Fa-f]+: ([0-9A-Fa-f ]+)\|", report, re.MULTILINE)
    payload = bytes.fromhex("".join(rows))
    assert len(payload) == int(size)
    return payload


def inspect(artifact, payload, exported, expected_payload, expected_exports):
    assert payload == expected_payload, artifact
    assert exported == expected_exports, (artifact, exported)
    return {
        "artifact_sha256": digest(artifact.read_bytes()),
        "contract_sha256": digest(payload) if payload is not None else None,
        "exports": sorted(exported),
    }


def observe_linux(artifact, interfaces):
    library = ctypes.CDLL(str(artifact))
    mismatches = []
    count = 0
    for interface in interfaces:
        function = getattr(library, interface["binding"])
        function.argtypes = [ctypes.c_uint32]
        function.restype = ctypes.c_uint32
        low, high = interface["requires"]
        for operand in range(low, high + 1):
            rule = interface["ensures"]
            expected = operand + rule["add"] if "add" in rule else operand * rule["multiply"]
            actual = function(operand)
            count += 1
            if actual != expected:
                mismatches.append({"binding": interface["binding"], "input": operand,
                                   "expected": expected, "actual": actual})
    return {"calls": count, "mismatches": mismatches}


def build_elf(work, payload, interfaces, exports):
    def compile_elf(output, *inputs):
        run("gcc", "-fuse-ld=bfd", "-shared", "-O2", "-fPIC", "-fvisibility=hidden",
            "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
            "-Wl,--build-id=none", "provider.c", *inputs, "-o", output, cwd=work)

    run("gcc", "-c", "contracts.S", "-o", "contracts.o", cwd=work)
    compile_elf("provider.so", "contracts.o")
    compile_elf("missing.so")
    compile_elf("wrong.so", "-DWRONG_RESERVATION", "contracts.o")
    run("strip", "--strip-all", "-o", "stripped.so", "provider.so", cwd=work)
    run("strip", "--strip-all", "--strip-section-headers",
        "-o", "sectionless.so", "provider.so", cwd=work)

    results = {}
    for name in ("provider", "stripped", "sectionless", "missing", "wrong"):
        artifact = work / f"{name}.so"
        notes = run("readelf", "-n", artifact)
        symbols = run("objdump", "-T", artifact)
        exported = set(re.findall(r"\b(fixture_\w+)$", symbols, re.MULTILINE))
        if name == "sectionless":
            assert "found at file offset" in notes
            assert re.search(r"Start of section headers:\s+0 ", run("readelf", "-hW", artifact))
        results[name] = inspect(
            artifact, elf_contract(notes), exported, None if name == "missing" else payload, exports,
        )
    for name, expected_mismatches in (("sectionless", 0), ("wrong", 8)):
        behavior = observe_linux(work / f"{name}.so", interfaces)
        assert behavior["calls"] == 16 and len(behavior["mismatches"]) == expected_mismatches
        results[name]["behavior"] = behavior
    return results


def build_pe(work, clang, lld, llvm, payload, exports):
    run(llvm / "llvm-rc", "/no-preprocess", "/FO", "contracts.res", "contracts.rc", cwd=work)
    results = {}
    for arch, machine in (("x86_64", "AMD64"), ("aarch64", "ARM64")):
        run(clang, "-target", f"{arch}-pc-windows-msvc", "-O2", "-c", "provider.c",
            "-mno-incremental-linker-compatible", "-o", "windows.obj", cwd=work)
        for variant, resources in (("embedded", ("contracts.res",)), ("missing", ())):
            artifact = work / f"provider-{arch}-{variant}.dll"
            run(lld / "lld-link", "/dll", "/noentry", "/nodefaultlib", "/opt:ref",
                "/timestamp:0", f"/out:{artifact.name}", "windows.obj", *resources, cwd=work)
            report = run(llvm / "llvm-readobj", "--file-headers", "--coff-exports",
                         "--coff-resources", artifact)
            assert f"Machine: IMAGE_FILE_MACHINE_{machine} " in report
            assert "IMAGE_FILE_DLL " in report
            exported = set(re.findall(r"^  Name: (fixture_\w+)$", report, re.MULTILINE))
            results[f"{arch}-{variant}"] = inspect(
                artifact, pe_contract(report), exported, payload if resources else None, exports,
            )
    return results


def build_macho(work, clang, lld, llvm, payload, exports):
    def audit(artifact, expected_payload):
        report = run(llvm / "llvm-objdump", "--macho", "--exports-trie", artifact)
        exported = set(re.findall(r"\s_(fixture_\w+)$", report, re.MULTILINE))
        headers = run(llvm / "llvm-objdump", "--macho", "--private-headers", artifact)
        extracted = None
        if "__llm_contract" in headers:
            run(llvm / "llvm-objcopy", "--dump-section=__TEXT,__llm_contract=extracted.json",
                artifact, work / "copy.dylib", cwd=work)
            extracted = (work / "extracted.json").read_bytes()
        return inspect(artifact, extracted, exported, expected_payload, exports)

    results = {}
    slices = []
    for arch in ("x86_64", "arm64"):
        run(clang, "-target", f"{arch}-apple-macos13", "-O2", "-fvisibility=hidden",
            "-c", "provider.c", "-o", "apple.o", cwd=work)
        for variant, section in (
            ("embedded", ("-sectcreate", "__TEXT", "__llm_contract", "contracts.json")),
            ("missing", ()),
        ):
            artifact = work / f"libprovider-{arch}-{variant}.dylib"
            run(lld / "ld64.lld", "-dylib", "-arch", arch, "-platform_version", "macos", "13.0",
                "13.0", "-dead_strip", "-S", "-adhoc_codesign", "-install_name",
                "@rpath/libprovider.dylib", *section, "-o", artifact.name, "apple.o", cwd=work)
            results[f"{arch}-{variant}"] = audit(artifact, payload if section else None)
            if section:
                slices.append((arch, artifact))
    universal = work / "libprovider.dylib"
    run(llvm / "llvm-lipo", "-create", *(artifact for _, artifact in slices), "-output", universal)
    results["universal_sha256"] = digest(universal.read_bytes())
    for arch, original in slices:
        thin = work / f"universal-{arch}.dylib"
        run(llvm / "llvm-lipo", universal, "-thin", arch, "-output", thin)
        assert thin.read_bytes() == original.read_bytes()
        results[f"universal-{arch}"] = audit(thin, payload)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", type=Path, required=True)
    parser.add_argument("--lld-bin", type=Path, required=True)
    parser.add_argument("--llvm-bin", type=Path, required=True)
    args = parser.parse_args()
    clang, lld, llvm = args.clang.resolve(), args.lld_bin.resolve(), args.llvm_bin.resolve()
    assert sys.platform == "linux" and platform.machine() == "x86_64"
    evidence = {
        "host": platform.system() + " " + platform.machine(),
        "python": platform.python_version(),
        "tools": {
            str(Path(tool).name): run(tool, "--version").splitlines()[0]
            for tool in ("gcc", "ld.bfd", "readelf", "objdump", "strip", clang, lld / "lld-link",
                         lld / "ld64.lld", llvm / "llvm-readobj")
        },
        "fixture_sha256": {name: digest((HERE / name).read_bytes()) for name in FIXTURES},
    }
    with tempfile.TemporaryDirectory(prefix="llmlang-native-contract-") as directory:
        work = Path(directory)
        for name in FIXTURES:
            shutil.copyfile(HERE / name, work / name)
        payload = (work / "contracts.json").read_bytes()
        interfaces = json.loads(payload)["interfaces"]
        assert len({item["id"] for item in interfaces}) == len(interfaces) == 2
        exports = {item["binding"] for item in interfaces}
        evidence["elf"] = build_elf(work, payload, interfaces, exports)
        evidence["pe"] = build_pe(work, clang, lld, llvm, payload, exports)
        evidence["macho"] = build_macho(work, clang, lld, llvm, payload, exports)
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
