"""Check copied, zeroed and retained Cortex-M3 sections on explicit re-entry."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import runpy
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
REFERENCE = runpy.run_path(str(HERE.parent / "cortex-m3-closure/run.py"))
PROFILES = {
    "exact_sections": (0, "20c 207!"),
    "clear_through_retained": (1, "200 200!"),
    "omit_copy": (2, "a0c 507!"),
    "omit_clear": (3, "2bc 267!"),
}
SECTION = re.compile(r"\[\s*\d+\]\s+(\.data|\.bss|\.noinit)\s+(\w+)\s+(\w+)\s+\w+\s+(\w+)")


def command(*args):
    return subprocess.check_output([str(arg) for arg in args], text=True, timeout=30)


def study(args):
    profiles = {}
    with TemporaryDirectory() as temporary:
        work = Path(temporary)
        for label, (number, expected) in PROFILES.items():
            obj = work / f"{label}.o"
            image = work / f"{label}.elf"
            source = work / f"{label}.s"
            command(args.clang, "-E", "-P", "-x", "assembler-with-cpp",
                    f"-DPROFILE={number}", HERE / "startup.S", "-o", source)
            command(args.assembler, "-triple=thumbv7m-none-eabi", "-mcpu=cortex-m3",
                    "-filetype=obj", source, "-o", obj)
            command(args.linker, "-T", HERE / "memory.ld", "--no-undefined", "-o", image, obj)
            content = command(args.readelf, "-SW", image)
            sections = {
                name: {"type": kind, "address": int(address, 16), "length": int(size, 16)}
                for name, kind, address, size in SECTION.findall(content)
            }
            assert sections == {
                ".data": {"type": "PROGBITS", "address": 0x20000000, "length": 4},
                ".bss": {"type": "NOBITS", "address": 0x20000004, "length": 4},
                ".noinit": {"type": "NOBITS", "address": 0x20000008, "length": 4},
            }, content
            trace = REFERENCE["boot"](args.qemu, image)
            assert trace == expected, (label, trace)
            profiles[label] = {
                "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                "sections": sections,
                "uart": trace,
            }
    return {
        "python": platform.python_version(),
        "qemu": command(args.qemu, "--version").splitlines()[0],
        "clang": command(args.clang, "--version").splitlines()[0],
        "assembler": command(args.assembler, "--version").splitlines()[0:2],
        "linker": command(args.linker, "--version").splitlines()[0],
        "profiles": profiles,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--assembler", default="llvm-mc-19")
    parser.add_argument("--linker", default="ld.lld-19")
    parser.add_argument("--readelf", default="readelf")
    parser.add_argument("--qemu", default="qemu-system-arm")
    print(json.dumps(study(parser.parse_args()), indent=2, sort_keys=True))
