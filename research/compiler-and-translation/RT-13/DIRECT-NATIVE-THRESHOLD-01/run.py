"""Compare direct x86-64 encodings with a retained LLVM inline assembly operation."""

import argparse
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import re
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
HOST = HERE.parent / "LLVM-ROUNDING-LTO-01" / "host.c"
MODES = ("nearest", "upward", "downward", "toward-zero")
ROUTES = ("inline_literals", "keep_call", "inline_loads")


def run(*command):
    process = subprocess.run(command, text=True, capture_output=True, check=True, timeout=45)
    if process.stderr:
        raise ValueError(process.stderr)
    return process.stdout.strip()


def load_immediate(bits, register):
    return b"\x48\xb8" + bits.to_bytes(8, "little") + bytes.fromhex("66 48 0f 6e") + bytes([register])


def wrap(name, instructions):
    return "\n".join((
        f".globl {name}", f".type {name},@function", f"{name}:",
        ".cfi_startproc", *instructions, ".cfi_endproc", f".size {name},.-{name}",
    ))


def collect(args, scratch):
    code = load_immediate(0x3ff0000000000000, 0xc0) + load_immediate(0xbff0000000000000, 0xc8)
    code += bytes.fromhex("f2 0f 58 c1 c3")
    direct = ".byte " + ", ".join(hex(byte) for byte in code)
    folded = wrap("inline_literals", ("pxor %xmm0, %xmm0", "ret"))
    native = wrap("keep_call", (direct,))
    capsule = scratch / "capsule.S"
    capsule.write_text("\n".join((".text", folded, native, '.section .note.GNU-stack,"",@progbits', "")))
    host_object = scratch / "host.o"
    capsule_object = scratch / "capsule.o"
    run("cc", "-O2", "-std=c17", "-Wall", "-Wextra", "-Werror", "-c", HOST, "-o", host_object)
    run("cc", "-c", capsule, "-o", capsule_object)
    results = {}
    for profile in ("native", "full", "thin"):
        flags = [] if profile == "native" else [f"-flto={profile}"]
        executable = scratch / f"probe-{profile}"
        run(args.llvm_bin / "clang", "-O3", *flags, f"--ld-path={args.llvm_bin / 'ld.lld'}",
            "-Wl,--threads=1", HERE / "inline.ll", host_object, capsule_object, "-lm", "-o", executable)

        rows = {}
        observations = run(executable).splitlines()
        for ((index, mode), seed, route), line in zip(product(enumerate(MODES), (0, 1), ROUTES),
                                                      observations, strict=True):
            observed_mode, observed_seed, observed_route, result, flags_equal = line.split()
            expected = "8000000000000000" if mode == "downward" and route != "inline_literals" else "0000000000000000"
            if (observed_mode, observed_seed, observed_route, result, flags_equal) != (
                str(index), str(seed), route, expected, "1"
            ):
                raise ValueError((profile, route, line))
            rows[f"{mode}/{seed}/{route}"] = result
        lines = run("objdump", "-d", "--insn-width=16", executable)
        symbols = {}
        for route in ROUTES:
            body = re.search(rf"(?ms)^[0-9a-f]+ <{route}>:\n(.*?)(?:\n\n|\Z)", lines)
            if body is None:
                raise ValueError((profile, route))
            instructions = re.findall(r"(?m)^\s*[a-f0-9]+:\s+((?:[0-9a-f]{2} )+)\s+([^\n]+)", body[1])
            if not instructions or all(asm.strip() != "ret" for _, asm in instructions):
                raise ValueError((route, body[1]))
            # The symbol may be followed by alignment padding. Check only its executable body.
            count = next(i for i, (_, asm) in enumerate(instructions) if asm.strip() == "ret") + 1
            symbols[route] = bytes.fromhex("".join(raw for raw, _ in instructions[:count])).hex()
        if symbols["inline_loads"] != code.hex() or symbols["keep_call"] != code.hex():
            raise ValueError((profile, symbols))
        if symbols["inline_literals"] != "660fefc0c3":
            raise ValueError((profile, "incorrect positive-zero control", symbols))
        results[profile] = {"result_bits": rows, "flag_checks_passed": len(rows), "bytes_through_return": symbols}
    return {
        "tools": {
            "clang": run(args.llvm_bin / "clang", "--version").splitlines()[0],
            "lld": run(args.llvm_bin / "ld.lld", "--version"),
            "gcc": run("cc", "-dumpfullversion"),
            "binutils": run("objdump", "--version").splitlines()[0],
            "glibc": run("getconf", "GNU_LIBC_VERSION"),
        },
        "inputs_sha256": {path.name: sha256(path.read_bytes()).hexdigest() for path in
                          (HOST, HERE / "inline.ll", HERE / "run.py", capsule)},
        "profiles": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llvm-bin", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt13-direct-native-") as directory:
        evidence = collect(args, Path(directory))
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
