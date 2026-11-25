"""Record object-level C ABI checks and prior execution scope for all hosted FFI cells."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import struct
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROFILES = [
    ("linux-x86_64", "x86_64-linux-gnu", "ELF", "System V AMD64", "Linux 6.18.57 guest or host scope", "glibc 2.41"),
    ("linux-aarch64", "aarch64-linux-gnu", "ELF", "AAPCS64", "Debian cross sysroot", "glibc 2.41"),
    ("linux-riscv64", "riscv64-linux-gnu", "ELF", "RISC-V LP64D", "Debian cross sysroot", "glibc 2.41"),
    ("macos-x86_64", "x86_64-apple-macos13.0", "Mach-O", "Apple x86-64", "macOS deployment 13.0", "libSystem"),
    ("macos-aarch64", "arm64-apple-macos13.0", "Mach-O", "Apple ARM64", "macOS deployment 13.0", "libSystem"),
    ("windows-x86_64", "x86_64-pc-windows-msvc", "COFF", "Microsoft x64", "Windows SDK version unselected", "UCRT/MSVC"),
    ("windows-aarch64", "aarch64-pc-windows-msvc", "COFF", "Windows ARM64", "Windows SDK version unselected", "UCRT/MSVC"),
    ("freebsd-x86_64", "x86_64-unknown-freebsd14.4", "ELF", "FreeBSD amd64", "FreeBSD 14.4 target spelling", "FreeBSD libc"),
    ("freebsd-aarch64", "aarch64-unknown-freebsd14.4", "ELF", "FreeBSD AArch64", "FreeBSD 14.4 target spelling", "FreeBSD libc"),
    ("android-x86_64", "x86_64-linux-android29", "ELF", "Android x86_64", "Android API level 29 target spelling", "Bionic"),
    ("android-aarch64", "aarch64-linux-android29", "ELF", "Android arm64-v8a", "Android API level 29 target spelling", "Bionic"),
    ("ios-aarch64", "arm64-apple-ios16.0", "Mach-O", "Apple ARM64", "iOS deployment 16.0", "libSystem"),
    ("openbsd-x86_64", "x86_64-unknown-openbsd7.7", "ELF", "OpenBSD amd64", "OpenBSD 7.7 target spelling", "OpenBSD libc"),
    ("openbsd-aarch64", "aarch64-unknown-openbsd7.7", "ELF", "OpenBSD ARM64", "OpenBSD 7.7 target spelling", "OpenBSD libc"),
    ("netbsd-x86_64", "x86_64-unknown-netbsd10.1", "ELF", "NetBSD amd64", "NetBSD 10.1 target spelling", "NetBSD libc"),
    ("netbsd-aarch64", "aarch64-unknown-netbsd10.1", "ELF", "NetBSD AArch64", "NetBSD 10.1 target spelling", "NetBSD libc"),
]


def read_ledger(path):
    return json.loads((ROOT / path).read_text())["profiles"]


def host_scope():
    linux = read_ledger("FFI-LINUX-TRIPLE-REPLAY-01/evidence.json")
    mach = read_ledger("FFI-MACHO-PROFILES-01/evidence.json")
    windows = read_ledger("FFI-WINDOWS-COFF-PROFILES-01/evidence.json")
    assert len(linux) == len(mach) == 3 and len(windows) == 2
    result = {}
    for arch, cell in linux.items():
        result[f"linux-{arch}"] = {"execution": cell["execution"], "glibc": cell["glibc"],
                                   "libc_sha256": cell["glibc_sha256"], "loader_sha256": cell["loader_sha256"]}
    for key in ("macos-x86_64", "macos-aarch64", "ios-aarch64"):
        result[key] = {"execution": "cross-linked Mach-O", "sdk": "deployment metadata only"}
    for key in ("windows-x86_64", "windows-aarch64"):
        result[key] = {"execution": "cross-linked PE/COFF", "sdk": "cross-build without Windows SDK closure"}
    return result


def output(args):
    return subprocess.check_output(args, text=True, timeout=15)


def profile(clang, readobj, work, triple, fmt, model):
    name = "probe.obj" if fmt == "COFF" else "probe.o"
    artifact = work / name
    flags = [clang, f"--target={triple}", "-std=c17", "-ffreestanding", "-O2", "-fno-builtin"]
    if fmt == "COFF":
        flags.append("-mno-incremental-linker-compatible")
    source = str(HERE / "abi.c")
    long_size = 4 if model == "LLP64" else 8
    output([*flags, f"-DEXPECT_LONG={long_size}", "-c", source, "-o", artifact])
    raw = artifact.read_bytes()
    if fmt == "COFF":
        assert struct.unpack_from("<I", raw, 4)[0] == 0
    header = output([readobj, "--file-headers", artifact])
    match = re.search(r"(?m)^Format: (.+)$", header)
    assert match and fmt.lower() in match[1].lower()
    assert "AddressSize: 64bit" in header
    ir = output([*flags, f"-DEXPECT_LONG={long_size}", "-emit-llvm", "-S", source, "-o", "-"])
    layout = re.search(r'(?m)^target datalayout = "([^"]+)"$', ir)[1]
    declaration = next(line for line in ir.splitlines() if line.startswith("define ") and "@roundtrip(" in line)
    wrong = subprocess.run([*flags, f"-DEXPECT_LONG={12-long_size}", "-fsyntax-only", source],
                           text=True, capture_output=True, timeout=15, check=False)
    assert wrong.returncode and "target long width" in wrong.stderr
    return {"format": match[1], "llvm_layout": layout, "embedded_sret": "sret(" in declaration,
            "record": {"size": 16, "align": 8, "flags_offset": 8}, "pointer_bits": 64,
            "endian": "little", "long_bits": 8 * long_size, "wrong_long_model_refused": True,
            "object_sha256": sha256(raw).hexdigest()}


def check(clang, readobj):
    existing = host_scope()
    results = {}
    with TemporaryDirectory() as directory:
        for key, triple, fmt, abi, release, library in PROFILES:
            model = "LLP64" if fmt == "COFF" else "LP64"
            binary = profile(clang, readobj, Path(directory), triple, fmt, model)
            results[key] = {
                "triple": triple, "call_profile": abi, "deployment": release, "data_model": model,
                "declared_system_library": library, "new_observation": "object-only, no system headers or sysroot",
                "previous_observation": existing.get(key, {"execution": "untested", "sdk": "unverified"}),
                **binary,
            }
    assert len(results) == 16 and len(existing) == 8
    assert results["windows-x86_64"]["embedded_sret"] and not results["windows-aarch64"]["embedded_sret"]
    return {"clang": output([clang, "--version"]).splitlines()[0],
            "object_inspector": output([readobj, "--version"]).splitlines()[0],
            "fixture_sha256": sha256((HERE / "abi.c").read_bytes()).hexdigest(),
            "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(), "profiles": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", required=True)
    parser.add_argument("--readobj", required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.clang, args.readobj), indent=2, sort_keys=True))
