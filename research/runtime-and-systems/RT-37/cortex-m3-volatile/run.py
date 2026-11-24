#!/usr/bin/env python3
"""Check preservation of two read-to-clear Cortex-M3 SysTick accesses."""

import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
CLOSURE = HERE.parent / "cortex-m3-closure"
SPEC = importlib.util.spec_from_file_location("cortex_closure", CLOSURE / "run.py")
closure = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(closure)

ICOUNT = "shift=0,align=off,sleep=off"
VARIANTS = {
    "llvm-volatile-O0": ("llvm", True, 0, False, "B10!", 2),
    "llvm-plain-O0": ("llvm", False, 0, False, "B11!", 1),
    "llvm-volatile-O2": ("llvm", True, 2, False, "B10!", 2),
    "llvm-plain-O2": ("llvm", False, 2, False, "B11!", 1),
    "rust-volatile-O2": ("rust", True, 2, False, "B10!", 2),
    "rust-plain-O2": ("rust", False, 2, False, "B11!", 1),
    "rust-volatile-reset-O2": ("rust", True, 2, True, "B00!", 2),
}


def deterministic_emulator(command, work):
    emulator = shutil.which(command)
    if emulator is None:
        raise ValueError(f"Could not find emulator {command!r}")
    wrapper = work / "run-qemu"
    wrapper.write_text("#!/usr/bin/env python3\nimport os, sys\n"
                       f"os.execv({emulator!r}, [{emulator!r}, '-icount', {ICOUNT!r}, *sys.argv[1:]])\n",
                       encoding="utf-8")
    wrapper.chmod(0o700)
    return wrapper


def emit_startup(args, work, reset):
    source = work / f"startup-{reset}.s"
    binary = source.with_suffix(".o")
    content = (HERE / "startup.s").read_text(encoding="utf-8")
    if reset:
        content = ".set RESET_AFTER_LATCH, 1\n" + content
    source.write_text(content, encoding="utf-8")
    closure.assemble(args.mc, source, binary)
    return binary


def emit_pair(args, work, name, backend, volatile, level):
    suffix = "ll" if backend == "llvm" else "rs"
    source = work / f"{name}.{suffix}"
    binary = source.with_suffix(".o")
    contents = (HERE / f"pair.{suffix}").read_text(encoding="utf-8")
    old, new = ("load volatile i32", "load i32") if backend == "llvm" else ("read_volatile(csr)", "read(csr)")
    if contents.count(old) != 2:
        raise ValueError("Expected two explicit read sites")
    if not volatile:
        contents = contents.replace(old, new)
    ir_loads = None
    if backend == "llvm":
        optimized = closure.run([args.opt, f"-passes=verify,default<O{level}>,verify", "-S", "-o", "-", "-"],
                                input=contents, check=True).stdout
        source.write_text(optimized, encoding="utf-8")
        closure.compile_llvm(args.llc, source, binary, level)
        ir_loads = len(re.findall(r"\bload (?:volatile )?i32\b", optimized))
        if ir_loads != (1 if not volatile and level == 2 else 2):
            raise ValueError(f"Unexpected optimized-IR load count for {name}: {ir_loads}")
    else:
        source.write_text(contents, encoding="utf-8")
        closure.compile_rust(args.rustc, source, binary, level)
    return binary, ir_loads


def pair_loads(args, image):
    result = closure.output([args.objdump, "--disassemble-symbols=sample_pair", "--no-show-raw-insn",
                             "--triple=thumbv7m-none-eabi", image])
    if "<sample_pair>:" not in result:
        raise ValueError(f"Missing sample_pair in {image.name}")
    loads = []
    for line in result.splitlines():
        match = re.fullmatch(r"\s*[a-f0-9]+:\s+ldr(?:\.w)?\s+(r\d+),\s*\[(r\d+)\]\s*", line)
        if match:
            loads.append(f"ldr {match[1]}, [{match[2]}]")
    return loads


def compare(args):
    with TemporaryDirectory(prefix="llmlang-cortex-volatile-") as tmp:
        work = Path(tmp)
        qemu = deterministic_emulator(args.qemu, work)
        startup = {reset: emit_startup(args, work, reset) for reset in (False, True)}
        records = {}
        for name, (backend, volatile, level, reset, trace_expected, loads_expected) in VARIANTS.items():
            step, ir_loads = emit_pair(args, work, name, backend, volatile, level)
            image = work / f"{name}.elf"
            closure.link(args.lld, image, (startup[reset], step))
            exact = closure.inspect(args, image)
            loads = pair_loads(args, image)
            trace = closure.boot(qemu, image)
            if trace != trace_expected or len(loads) != loads_expected:
                raise ValueError(f"Unexpected {name} trace {trace!r}, word loads {loads!r}")
            records[name] = {"uart": trace, "optimized_llvm_ir_word_loads": ir_loads, "linked_word_loads": loads,
                             **{key: exact[key] for key in ("image_sha256", "flash_extent_bytes", "static_ram_bytes")}}
    inputs = {name: HERE / name for name in ("startup.s", "pair.ll", "pair.rs", "run.py")}
    inputs.update({"closure-run.py": CLOSURE / "run.py", "memory.ld": CLOSURE / "memory.ld"})
    return {"schema": "llmlang-cortex-m3-volatile-v1", "machine": "lm3s6965evb", "qemu_icount": ICOUNT,
            "tools": {name: closure.output([getattr(args, name), "--version"]).splitlines()[0].strip()
                      for name in ("opt", "objdump", "llc", "lld", "rustc", "qemu")},
            "source_sha256": {name: sha256(path.read_bytes()).hexdigest() for name, path in inputs.items()},
            "images": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, command in {
        "mc": "llvm-mc-19", "llc": "llc-19", "lld": "ld.lld-19", "readelf": "llvm-readelf-19",
        "nm": "llvm-nm-19", "objcopy": "llvm-objcopy-19", "objdump": "llvm-objdump-19",
        "opt": "opt-19", "rustc": "rustc", "qemu": "qemu-system-arm",
    }.items():
        parser.add_argument(f"--{name}", default=command)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(compare(args), indent=2) + "\n", encoding="utf-8")
