#!/usr/bin/env python3
"""Replay the shadow-stack probe on a Bochs Tiger Lake guest with CET."""

import argparse
import errno
import json
import os
from pathlib import Path
import pty
import re
import select
import shutil
import subprocess
import tempfile
import time

if __package__:
    from .run import DIRECTORY, KERNEL_RELEASE, KERNEL_SHA256, file_digest, initramfs, source_hashes, verify_probe
else:
    from run import DIRECTORY, KERNEL_RELEASE, KERNEL_SHA256, file_digest, initramfs, source_hashes, verify_probe


CASE = "shadow_stack_guest_owns_zeroed_mappings_without_restore_tokens"
BOOT_FILE_PINS = {
    "bochs": "5b8b1bbe782917bbe08c3511c0e74adb969b1ac86698ce823f396327689f3ebc",
    "bios": "920f0170ac61960e1fb8cbdbd7a8176b4238ea1b19619bf768bb076989a32614",
    "video_bios": "812a1ba3b1f5867089d90da22cff3253926cfe915f7c7cf58e267969cb512e47",
    "genisoimage": "fd29f111c051f915d74fe3481fc12f3de1fc6ce09c1a6f7ff3e2dad60ffd177a",
    "isolinux": "f3e2c1786564e148fb394e2321666ddccccedc18f7cf9db3e2416d45d13ea492",
    "ldlinux": "26cbd44c3a3dacbf3971cfbc04db539da07767fa00797f505044e2f68dcfae89",
    "term_gui": "5042105d2a53bab8286fd3360cf5898257114638b23aabaaced6255843ab3df4",
}
BOOT_CONFIG = """DEFAULT linux
PROMPT 0
TIMEOUT 1
SERIAL 0 115200
LABEL linux
  KERNEL /linux
  APPEND initrd=/initrd console=ttyS0,115200 loglevel=0 rdinit=/init panic=-1
"""


def boot(executable, plugin_dir, directory, timeout):
    master, slave = pty.openpty()
    try:
        with subprocess.Popen(
            [str(executable), "-q", "-f", "bochsrc", "-rc", "boot.rc"],
            cwd=directory, stdin=slave, stdout=slave, stderr=slave,
            env={**os.environ, "TERM": "xterm", "LTDL_LIBRARY_PATH": str(plugin_dir)},
        ) as emulator:
            os.close(slave)
            slave = None
            console = bytearray()
            deadline = time.monotonic() + timeout
            try:
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not select.select([master], [], [], remaining)[0]:
                        raise ValueError("Bochs guest boot timed out")
                    try:
                        output = os.read(master, 4096)
                    except OSError as error:
                        if error.errno != errno.EIO:
                            raise
                        break
                    if not output:
                        break
                    console.extend(output)
                return emulator.wait(timeout=max(0, deadline - time.monotonic())), console.decode(
                    "utf-8", errors="replace"
                )
            finally:
                if emulator.poll() is None:
                    emulator.kill()
    finally:
        os.close(master)
        if slave is not None:
            os.close(slave)


def replay(kernel, probe, bochs_root, iso_root, video_bios, cc, timeout, provider_root=None):
    bochs_root = bochs_root.resolve()
    iso_root = iso_root.resolve()
    video_bios = video_bios.resolve()
    if file_digest(kernel) != KERNEL_SHA256:
        raise ValueError("guest kernel SHA-256 does not match the supplied pin")
    executable = probe.read_bytes()
    verify_probe(executable)
    bochs = bochs_root / "usr/bin/bochs-bin"
    plugins = bochs_root / "usr/lib/x86_64-linux-gnu/bochs/plugins"
    bios = bochs_root / "usr/share/bochs/BIOS-bochs-latest"
    genisoimage = iso_root / "usr/bin/genisoimage"
    isolinux = iso_root / "usr/lib/ISOLINUX/isolinux.bin"
    ldlinux = iso_root / "usr/lib/syslinux/modules/bios/ldlinux.c32"
    boot_files = {
        "bochs": bochs, "bios": bios, "video_bios": video_bios, "genisoimage": genisoimage,
        "isolinux": isolinux, "ldlinux": ldlinux, "term_gui": plugins / "libbx_term_gui.so",
    }
    boot_hashes = {name: file_digest(path) for name, path in boot_files.items()}
    if boot_hashes != BOOT_FILE_PINS:
        mismatched = sorted(name for name in boot_hashes if boot_hashes[name] != BOOT_FILE_PINS[name])
        raise ValueError(f"Bochs boot file SHA-256 mismatch: {', '.join(mismatched)}")
    with tempfile.TemporaryDirectory(prefix="llmlang-shadow-stack-vm-") as temporary:
        directory = Path(temporary)
        media = directory / "media"
        loader = media / "isolinux"
        loader.mkdir(parents=True)
        shutil.copyfile(isolinux, loader / "isolinux.bin")
        shutil.copyfile(ldlinux, loader / "ldlinux.c32")
        shutil.copyfile(kernel, media / "linux")
        (loader / "isolinux.cfg").write_text(BOOT_CONFIG)
        init = directory / "init"
        subprocess.run(
            [cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-static",
             str(DIRECTORY / "init_bochs.c"), "-o", str(init)],
            check=True, timeout=30,
        )
        (media / "initrd").write_bytes(initramfs(init.read_bytes(), executable))
        subprocess.run(
            [str(genisoimage), "-o", "probe.iso", "-quiet", "-R", "-J", "-no-emul-boot",
             "-boot-load-size", "4", "-boot-info-table", "-b", "isolinux/isolinux.bin",
             "-c", "isolinux/boot.cat", "media"],
            cwd=directory, check=True, timeout=30,
        )
        (directory / "boot.rc").write_text("c\n")
        (directory / "bochsrc").write_text(
            f"""megs: 256
romimage: file={json.dumps(str(bios))}
vgaromimage: file={json.dumps(str(video_bios))}
cpu: model=tigerlake, count=1, ips=70000000
ata0-master: type=cdrom, path=probe.iso, status=inserted
boot: cdrom
log: bochs.log
panic: action=fatal
error: action=report
info: action=report
debug: action=ignore
display_library: term
com1: enabled=1, mode=file, dev=serial.log
"""
        )
        status, terminal = boot(bochs, plugins, directory, timeout)
        emulator_log = (directory / "bochs.log").read_text(errors="replace")
        serial_log = directory / "serial.log"
        console = serial_log.read_text(errors="replace") if serial_log.exists() else terminal
    # Bochs 2.7 reports a guest-requested ACPI shutdown as a fatal emulator exit.
    if status != 1 or ">>PANIC<< ACPI control: soft power off" not in emulator_log:
        raise ValueError(f"Bochs did not reach ACPI power-off (exit {status})\n{console}")
    markers = [line for line in console.splitlines() if line.startswith("LLMLANG_GUEST_")]
    if markers != [
        f"LLMLANG_GUEST_KERNEL {KERNEL_RELEASE}",
        f"LLMLANG_GUEST_CASE {CASE}",
        "LLMLANG_GUEST_RESULT 0",
    ]:
        raise ValueError(f"shadow-stack guest probe failed\n{console}")
    version = re.search(r"Bochs x86 Emulator [^\r\n]+", terminal)
    if not version:
        raise ValueError("missing Bochs version")
    report = {
        "kernel_release": KERNEL_RELEASE,
        "kernel_sha256": KERNEL_SHA256,
        "probe_sha256": file_digest(probe),
        "bochs": version.group(),
        "cpu": "tigerlake",
        "boot_files_sha256": boot_hashes,
        "guest_status": 0,
        "cases": [CASE],
    }
    if provider_root:
        report.update(source_hashes(provider_root, "shadow_stack_guest"))
        report["test_source_sha256"].update({
            "guest/init_bochs.c": file_digest(DIRECTORY / "init_bochs.c"),
            "guest/run_bochs.py": file_digest(DIRECTORY / "run_bochs.py"),
        })
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--bochs-root", type=Path, required=True)
    parser.add_argument("--iso-root", type=Path, required=True)
    parser.add_argument("--video-bios", type=Path, required=True)
    parser.add_argument("--cc", default="cc")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--provider-root", type=Path)
    args = parser.parse_args()
    try:
        evidence = replay(
            args.kernel, args.probe, args.bochs_root, args.iso_root,
            args.video_bios, args.cc, args.timeout, args.provider_root,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Bochs guest probe: {error}\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
