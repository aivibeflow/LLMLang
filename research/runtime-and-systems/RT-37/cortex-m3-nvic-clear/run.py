"""Check write-one-to-clear pending-bit semantics in pinned Cortex-M3 images."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import runpy
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
BUILD = runpy.run_path(str(HERE.parent / "cortex-m3-nested-stack/run.py"))
POLICIES = {
    "clear_selected_bit": (0, "332 331!"),
    "read_or_then_write_clear": (1, "330 330!"),
    "read_and_not_then_write_clear": (2, "331 332!"),
    "write_selected_bit_to_set_alias": (3, "333 333!"),
}


def study(args):
    command = BUILD["command"]
    boot = BUILD["REFERENCE"]["boot"]
    results = {}
    with TemporaryDirectory() as temporary:
        work = Path(temporary)
        for policy, (number, expected) in POLICIES.items():
            source = work / f"{policy}.s"
            obj = work / f"{policy}.o"
            elf = work / f"{policy}.elf"
            command(args.clang, "-E", "-P", "-x", "assembler-with-cpp",
                    f"-DPROFILE={number}", HERE / "pending.S", "-o", source)
            command(args.assembler, "-triple=thumbv7m-none-eabi", "-mcpu=cortex-m3",
                    "-filetype=obj", source, "-o", obj)
            command(args.linker, "-T", BUILD["LINKER_SCRIPT"], "--no-undefined", "-o", elf, obj)
            result = boot(args.qemu, elf)
            assert result == expected, (policy, result)
            rows = []
            for target, values in enumerate(result.removesuffix("!").split()):
                set_read, clear_read, remaining = map(int, values)
                rows.append({
                    "target_mask": 1 << target, "before_set_alias": set_read,
                    "before_clear_alias": clear_read, "after_pending": remaining,
                })
            results[policy] = {
                "image_sha256": hashlib.sha256(elf.read_bytes()).hexdigest(),
                "records": rows, "uart": result,
            }
    return {
        "python": platform.python_version(),
        "qemu": command(args.qemu, "--version").splitlines()[0],
        "clang": command(args.clang, "--version").splitlines()[0],
        "assembler": command(args.assembler, "--version").splitlines()[0],
        "linker": command(args.linker, "--version").splitlines()[0],
        "results": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--assembler", default="llvm-mc-19")
    parser.add_argument("--linker", default="ld.lld-19")
    parser.add_argument("--qemu", default="qemu-system-arm")
    print(json.dumps(study(parser.parse_args()), indent=2, sort_keys=True))
