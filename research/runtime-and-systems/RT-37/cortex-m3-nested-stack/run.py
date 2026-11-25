"""Compare explicit Cortex-M3 priority and masking schedules in QEMU."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import runpy
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
REFERENCE = runpy.run_path(str(HERE.parent / "cortex-m3-closure/run.py"))
LINKER_SCRIPT = HERE.parent / "cortex-m3-startup-retention/memory.ld"
PROFILES = {
    "higher_priority": (0, "LHl 20 40!"),
    "equal_priority": (1, "LlH 20 20!"),
    "unmask_inside_handler": (2, "LlH 20 40!"),
    "unmask_in_thread": (3, "LlH 20 20!"),
}


def command(*args):
    return subprocess.check_output([str(arg) for arg in args], text=True, timeout=30)


def study(args):
    results = {}
    with TemporaryDirectory() as temporary:
        work = Path(temporary)
        for name, (index, expected) in PROFILES.items():
            source = work / f"{name}.s"
            assembly = work / f"{name}.o"
            image = work / f"{name}.elf"
            command(args.clang, "-E", "-P", "-x", "assembler-with-cpp",
                    f"-DPROFILE={index}", HERE / "nested.S", "-o", source)
            command(args.assembler, "-triple=thumbv7m-none-eabi", "-mcpu=cortex-m3",
                    "-filetype=obj", source, "-o", assembly)
            command(args.linker, "-T", LINKER_SCRIPT, "--no-undefined", "-o", image, assembly)
            observed = REFERENCE["boot"](args.qemu, image)
            assert observed == expected, (name, observed)
            trace, low, high = observed.removesuffix("!").split()
            results[name] = {
                "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                "trace": trace, "pendsv_frame_bytes": int(low, 16), "systick_frame_bytes": int(high, 16),
                "peak_frame_bytes": max(int(low, 16), int(high, 16)),
            }
    return {
        "python": platform.python_version(),
        "qemu": command(args.qemu, "--version").splitlines()[0],
        "clang": command(args.clang, "--version").splitlines()[0],
        "assembler": command(args.assembler, "--version").splitlines()[0],
        "linker": command(args.linker, "--version").splitlines()[0],
        "profiles": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--assembler", default="llvm-mc-19")
    parser.add_argument("--linker", default="ld.lld-19")
    parser.add_argument("--qemu", default="qemu-system-arm")
    print(json.dumps(study(parser.parse_args()), indent=2, sort_keys=True))
