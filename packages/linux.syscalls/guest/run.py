#!/usr/bin/env python3
"""Run a trusted static Linux x86-64 probe in a disposable QEMU guest."""

import argparse
import hashlib
import json
import lzma
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(DIRECTORY.parent))

from package import PackageError, provider_files  # noqa: E402

KERNEL_RELEASE = "6.12.117+deb13-cloud-amd64"
KERNEL_SHA256 = "ed8f0dbdbefe3994093937f5ee934818ae902b88cb0b6bc423811c10d55b87b0"
QUOTA_IMAGE_SHA256 = "fb7ca83c1f15ab4d2752c643b0af386dc4eaa7adecda5332e0d0db478755c378"
MKE2FS_VERSIONS = {"1.47.0", "1.47.2"}
MODULE_FIXTURES = {
    "loop.ko": (
        "drivers/block/loop.ko.xz",
        "f566d2236415f990fa3c0d44c88249c2313a072881d94c65e4d583af34d61804",
        "a56c845f09205ee3d7d951990dec12a4942d73ca01525d5cdce7b1f265dbf504",
    ),
    "quota_tree.ko": (
        "fs/quota/quota_tree.ko.xz",
        "9faa48fdd03608cb10a7f14d62c63fbe9fee2cdf4728003d3d7e2361941d1a00",
        "4c46048c5af6aed64b346e0f736dd34d2eb0739bbc3c1ab984664ac72b9587c0",
    ),
    "quota_v2.ko": (
        "fs/quota/quota_v2.ko.xz",
        "a0afc13cf118b8b4033bced626b730eb76b16ae0542c0a1b80b7446394322f52",
        "abdb0911d395b698d3c1257090dd16cea667382fe538daba0a3d49157d2403b7",
    ),
}


def cpio_record(number, name, mode, data):
    name = name.encode("ascii") + b"\0"
    fields = (number, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(name), 0)
    header = b"070701" + b"".join(f"{field:08x}".encode("ascii") for field in fields)
    record = header + name
    return record + b"\0" * (-len(record) % 4) + data + b"\0" * (-len(data) % 4)


def initramfs(init, probe, fixtures=()):
    records = [cpio_record(1, "init", 0o100755, init), cpio_record(2, "probe", 0o100755, probe)]
    for number, (name, data) in enumerate(fixtures, 3):
        records.append(cpio_record(number, name, 0o100444, data))
    records.append(cpio_record(len(records) + 1, "TRAILER!!!", 0, b""))
    return b"".join(records)


def module_hashes(names):
    return {
        name: {"archive": MODULE_FIXTURES[name][1], "elf": MODULE_FIXTURES[name][2]}
        for name in names
    }


def module_payloads(root, names):
    if names and root is None:
        raise ValueError("the selected suite requires --module-archive-root")
    for name, hashes in module_hashes(names).items():
        archive = (root / MODULE_FIXTURES[name][0]).read_bytes()
        if hashlib.sha256(archive).hexdigest() != hashes["archive"]:
            raise ValueError(f"guest module archive hash mismatch for {name}")
        module = lzma.decompress(archive)
        if hashlib.sha256(module).hexdigest() != hashes["elf"]:
            raise ValueError(f"guest module ELF hash mismatch for {name}")
        yield name, module

def quota_filesystem(directory, mke2fs):
    version = subprocess.check_output([mke2fs, "-V"], stderr=subprocess.STDOUT, text=True, timeout=10)
    match = re.match(r"mke2fs (\S+)", version)
    if match is None or match.group(1) not in MKE2FS_VERSIONS:
        raise ValueError("quota guest requires e2fsprogs mke2fs 1.47.0 or 1.47.2")
    image = directory / "quota.ext4"
    subprocess.run(
        [mke2fs, "-q", "-F", "-t", "ext4", "-b", "1024", "-O", "none,quota", "-m", "0",
         "-E", "lazy_itable_init=0,quotatype=usrquota,hash_seed=891c9416-aa66-4ab8-980d-59c58024396f",
         "-U", "77be2ce1-5861-4bfb-ba4e-88b5c22de211", "-L", "llmlang-quota", str(image), "4096"],
        env={**os.environ, "MKE2FS_CONFIG": "/dev/null", "E2FSPROGS_FAKE_TIME": "1700000000"},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=30,
    )
    data = image.read_bytes()
    if hashlib.sha256(data).hexdigest() != QUOTA_IMAGE_SHA256:
        raise ValueError("generated ext4 quota image differs from the pin")
    return "quota.ext4", data


def verify_probe(probe):
    if len(probe) < 64 or probe[:7] != b"\x7fELF\x02\x01\x01":
        raise ValueError("probe must be a native 64-bit little-endian ELF")
    if struct.unpack_from("<H", probe, 18)[0] != 62:
        raise ValueError("probe must target native x86-64")
    offset = struct.unpack_from("<Q", probe, 32)[0]
    entry_size, entries = struct.unpack_from("<HH", probe, 54)
    if entry_size != 56 or entries < 1 or offset + entry_size * entries > len(probe):
        raise ValueError("invalid ELF program headers")
    if any(struct.unpack_from("<I", probe, offset + entry_size * i)[0] == 3 for i in range(entries)):
        raise ValueError("probe has a dynamic interpreter; build a static executable")


def file_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes(provider_root, provider_example):
    if not re.fullmatch(r"[a-z][a-z0-9_]*", provider_example):
        raise ValueError("invalid provider example name")
    example = f"examples/{provider_example}.rs"
    provider = {
        name: hashlib.sha256(data).hexdigest() for name, data in provider_files(provider_root).items()
    }
    tests = {
        "guest/init.c": file_digest(DIRECTORY / "init.c"),
        "guest/run.py": file_digest(DIRECTORY / "run.py"),
        f"provider/{example}": file_digest(provider_root / example),
    }
    return {"provider_source_sha256": provider, "test_source_sha256": tests}


def run(
    kernel, kernel_hash, probe, *, qemu, cc, bios=None, firmware=None,
    timeout=60, expected_cases=(), cpu=None, numa=False, module_root=None, modules=(), quota_image=False, mke2fs="mke2fs",
):
    if file_digest(kernel) != kernel_hash:
        raise ValueError("guest kernel SHA-256 does not match the supplied pin")
    executable = probe.read_bytes()
    verify_probe(executable)
    fixtures = tuple(module_payloads(module_root, modules))
    with tempfile.TemporaryDirectory(prefix="llmlang-syscalls-vm-") as temporary:
        directory = Path(temporary)
        init = directory / "init"
        archive = directory / "initramfs.cpio"
        subprocess.run(
            [cc, "-O2", "-Wall", "-Wextra", "-Werror", "-static", str(DIRECTORY / "init.c"), "-o", str(init)],
            check=True, timeout=30,
        )
        if quota_image:
            fixtures += (quota_filesystem(directory, mke2fs),)
        archive.write_bytes(initramfs(init.read_bytes(), executable, fixtures))
        command = [
            qemu, "-no-user-config", "-nodefaults", "-machine", "q35", "-accel", "tcg",
            "-m", "256", "-smp", "1", "-nographic", "-monitor", "none", "-serial", "stdio",
            "-nic", "none", "-no-reboot", "-sandbox",
            "on,obsolete=deny,elevateprivileges=deny,spawn=deny,resourcecontrol=deny",
            "-kernel", str(kernel), "-initrd", str(archive),
            "-append", "console=ttyS0 loglevel=3 rdinit=/init panic=-1",
        ]
        if numa:
            command.extend((
                "-object", "memory-backend-ram,id=node0,size=128M",
                "-object", "memory-backend-ram,id=node1,size=128M",
                "-numa", "node,nodeid=0,cpus=0,memdev=node0",
                "-numa", "node,nodeid=1,memdev=node1",
            ))
        if cpu:
            command.extend(("-cpu", cpu))
        if bios:
            command.extend(("-bios", str(bios)))
        if firmware:
            command.extend(("-L", str(firmware)))
        boot = subprocess.run(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, encoding="utf-8", errors="replace", timeout=timeout,
        )
    console = boot.stdout.splitlines()
    releases = [line.removeprefix("LLMLANG_GUEST_KERNEL ") for line in console
                if line.startswith("LLMLANG_GUEST_KERNEL ")]
    statuses = [line for line in console if re.fullmatch(r"LLMLANG_GUEST_RESULT \d+", line)]
    cases = [line.removeprefix("LLMLANG_GUEST_CASE ") for line in console
             if re.fullmatch(r"LLMLANG_GUEST_CASE [a-z][a-z0-9_]*", line)]
    if boot.returncode or len(releases) != 1 or len(statuses) != 1 or statuses[0] != "LLMLANG_GUEST_RESULT 0":
        raise ValueError(f"guest probe did not complete successfully (QEMU exit {boot.returncode})\n{boot.stdout}")
    if len(set(cases)) != len(cases):
        raise ValueError("guest probe reported duplicate cases")
    if expected_cases and set(cases) != set(expected_cases):
        raise ValueError(f"guest cases differ from expectation: {sorted(cases)}")
    return {
        "kernel_release": releases[0],
        "kernel_sha256": kernel_hash,
        "probe_sha256": hashlib.sha256(executable).hexdigest(),
        "qemu": subprocess.check_output([qemu, "--version"], text=True, timeout=10).splitlines()[0],
        "firmware_sha256": file_digest(bios) if bios else None,
        "cpu": cpu,
        "numa": numa,
        "module_fixtures_sha256": module_hashes(modules),
        "quota_image_sha256": QUOTA_IMAGE_SHA256 if quota_image else None,
        "guest_status": 0,
        "cases": sorted(cases),
    }, boot.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, required=True, help="x86-64 Linux bzImage")
    parser.add_argument("--kernel-sha256", required=True, help="SHA-256 pin for the bzImage")
    parser.add_argument("--probe", type=Path, required=True, help="trusted static x86-64 test executable")
    parser.add_argument("--qemu", default="qemu-system-x86_64")
    parser.add_argument("--cpu", choices=("max",), help="guest CPU model for feature-specific probes")
    parser.add_argument("--numa", action="store_true", help="split guest RAM into two NUMA nodes")
    parser.add_argument("--module-archive-root", type=Path, help="pinned guest module kernel directory")
    parser.add_argument("--module", choices=MODULE_FIXTURES, action="append", default=[])
    parser.add_argument("--quota-image", action="store_true", help="include the pinned ext4 quota fixture")
    parser.add_argument("--mke2fs", default="mke2fs")
    parser.add_argument("--cc", default="cc", help="C compiler with static libc")
    parser.add_argument("--bios", type=Path, help="explicit QEMU BIOS image")
    parser.add_argument("--firmware", type=Path, help="explicit QEMU firmware directory")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--expect-case", action="append", default=[], help="require a named guest case")
    parser.add_argument("--provider-root", type=Path, help="record the Rust provider and probe source digests")
    parser.add_argument("--provider-example", default="uts_guest", help="name of the selected Rust example")
    parser.add_argument("--verbose", action="store_true", help="include the guest console")
    args = parser.parse_args()
    try:
        evidence, console = run(
            args.kernel, args.kernel_sha256, args.probe, qemu=args.qemu,
            cc=args.cc, bios=args.bios, firmware=args.firmware, timeout=args.timeout,
            expected_cases=args.expect_case, cpu=args.cpu, numa=args.numa,
            module_root=args.module_archive_root, modules=args.module,
            quota_image=args.quota_image, mke2fs=args.mke2fs,
        )
        if args.provider_root:
            evidence.update(source_hashes(args.provider_root, args.provider_example))
    except (OSError, PackageError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"guest probe: {error}\n")
    if args.verbose:
        print(console, end="")
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
