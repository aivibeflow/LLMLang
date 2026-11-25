"""Boot independently linked assembly and LLVM RV64 HALs in the same Sv39 workload."""

import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "riscv-trap-isolation"
REMAP = HERE.parent / "riscv-sv39-remap"
HAL = HERE.parent / "RV64-HAL-INTRINSICS-01"
TARGET = "riscv64-unknown-none-elf"
FEATURES = "+zicsr,+zifencei"
WORDS = {
    "read_sp": ["00010513", "00008067"],
    "memory_barrier": ["0330000f", "00008067"],
    "translation_barrier": ["12000073", "00008067"],
}


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def run(*command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=25)
    assert result.returncode == 0 and not result.stderr, (
        command, result.returncode, result.stdout, result.stderr,
    )
    return result.stdout


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def compile_assembly(args, source, obj):
    run(args.mc, "-triple", TARGET, f"-mattr={FEATURES}", "-filetype=obj", source, "-o", obj)


def linked_words(args, image):
    result = {}
    for name in WORDS:
        disassembly = run(args.objdump, "-d", f"--disassemble-symbols={name}", image)
        rows = re.findall(r"(?m)^\s*[a-f0-9]+:\s+([a-f0-9]{8})\b", disassembly)
        assert len(rows) == 2, (name, disassembly)
        result[name] = rows
    relocations = run(args.readelf, "-rW", image)
    assert "There are no relocations" in relocations
    return result


def collect(args, work):
    isolated = module("isolated_elf", BASE / "run.py")
    remap = module("rv64_remap_transform", REMAP / "transform.py")
    start = remap.render((BASE / "boot.s").read_text(encoding="utf-8"), 0)
    start = remap.replace_once(
        start, "  la sp, machine_stack_top\n",
        "  la sp, machine_stack_top\n  call read_sp\n  bne a0, sp, fail\n"
        "  li a0, 'H'\n  call uart_byte\n",
    )
    begin = start.index("synchronize_translation:\n")
    end = start.index(".size synchronize_translation,", begin)
    start = start[:begin] + """synchronize_translation:
  addi sp, sp, -16
  sd ra, 8(sp)
  call memory_barrier
  call translation_barrier
  ld ra, 8(sp)
  addi sp, sp, 16
  ret
""" + start[end:]
    source = work / "start.s"
    source.write_text(start, encoding="utf-8")
    boot = work / "start.o"
    compile_assembly(args, source, boot)

    layout = work / "memory.ld"
    layout.write_text(remap.replace_once(
        (BASE / "memory.ld").read_text(encoding="utf-8"), "*(.text.trap)",
        "*(.text.trap) *(.text .text.*)",
    ), encoding="utf-8")
    variants = {}
    for name, leaf in (
        ("assembly", (HAL / "hal.s").read_text(encoding="utf-8")),
        ("wrong-stack", (HAL / "hal.s").read_text(encoding="utf-8").replace("mv a0, sp", "addi a0, sp, 16")),
        ("wrong-fence", (HAL / "hal.s").read_text(encoding="utf-8").replace("sfence.vma", "fence rw, rw")),
    ):
        asm = work / f"{name}.s"
        obj = work / f"{name}.o"
        asm.write_text(leaf, encoding="utf-8")
        compile_assembly(args, asm, obj)
        variants[name] = obj
    for profile in ("O0", "O2", "O3"):
        optimized = work / f"{profile}.ll"
        obj = work / f"{profile}.o"
        run(args.opt, f"-passes=verify,default<{profile}>,verify", "-S", HAL / "hal.ll", "-o", optimized)
        run(args.llc, f"-mtriple={TARGET}", f"-mattr={FEATURES}", f"-{profile}",
            "-filetype=obj", optimized, "-o", obj)
        variants[f"llvm-{profile}"] = obj

    records = {}
    for name, variant in variants.items():
        image = work / f"{name}.elf"
        run(args.lld, "--no-undefined", "--no-relax", "-T", layout, boot, variant, "-o", image)
        facts = isolated.check_elf(args, image, paged=True)
        words = linked_words(args, image)
        expected_words = {key: value.copy() for key, value in WORDS.items()}
        expected_trace = "HBEISRAMBDPZ!"
        if name == "wrong-stack":
            expected_words["read_sp"][0] = "01010513"
            expected_trace = "X"
        if name == "wrong-fence":
            expected_words["translation_barrier"][0] = "0330000f"
            expected_trace = "HBEISRAMADA!"
        assert words == expected_words, (name, words)
        qemu = [args.qemu]
        if args.qemu_data is not None:
            qemu.extend(["-L", args.qemu_data])
        actual = run(
            *qemu, "-machine", "virt", "-cpu", "rv64", "-m", "64M", "-smp", "1",
            "-bios", "none", "-nodefaults", "-display", "none", "-monitor", "none",
            "-serial", "stdio", "-kernel", image,
        )
        assert actual == expected_trace, (name, actual)
        records[name] = {
            "uart": actual, "leaf_words": words,
            "elf_sha256": facts["elf_sha256"], "user_compartment_sha256": facts["user_code_sha256"],
            "load_regions": facts["loads"],
        }
    assert len({row["user_compartment_sha256"] for row in records.values()}) == 1
    sources = (BASE / "boot.s", BASE / "memory.ld", BASE / "run.py", REMAP / "transform.py",
               HAL / "hal.s", HAL / "hal.ll", HERE / "run.py")
    return {
        "machine": "riscv64 virt rv64 single-hart QEMU",
        "versions": {
            name: run(getattr(args, name), "--version").splitlines()[0]
            for name in ("qemu", "opt", "llc", "mc", "lld", "objdump")
        },
        "qemu_sha256": digest(Path(shutil.which(args.qemu)).resolve()),
        "source_sha256": {f"{path.parent.name}/{path.name}": digest(path) for path in sources},
        "generated_sha256": {"boot": digest(source), "layout": digest(layout)},
        "profiles": records,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, binary in (
        ("mc", "llvm-mc-19"), ("opt", "opt-19"), ("llc", "llc-19"), ("lld", "ld.lld-19"),
        ("readelf", "llvm-readelf-19"), ("nm", "llvm-nm-19"),
        ("objcopy", "llvm-objcopy-19"), ("objdump", "llvm-objdump-19"),
        ("qemu", "qemu-system-riscv64"),
    ):
        parser.add_argument(f"--{name}", default=binary)
    parser.add_argument("--qemu-data", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt38-hal-live-") as scratch:
        evidence = collect(args, Path(scratch))
    args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
