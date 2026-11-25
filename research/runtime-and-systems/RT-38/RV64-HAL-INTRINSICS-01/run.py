"""Compare exact linked RV64 HAL operations and check freestanding closure."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
TARGET = "riscv64-unknown-none-elf"
FEATURES = "+zicsr,+zifencei"
EXPECTED = {
    "read_sp": ("00010513", "00008067"),
    "memory_barrier": ("0330000f", "00008067"),
    "translation_barrier": ("12000073", "00008067"),
}


def run(*command):
    result = subprocess.run(command, text=True, capture_output=True, check=True, timeout=30)
    if result.stderr:
        raise ValueError(result.stderr)
    return result.stdout


def assemble(source, path):
    run("llvm-mc-19", "-triple", TARGET, f"-mattr={FEATURES}", "-filetype=obj", "-o", path, source)


def compile_ir(source, path, optimization):
    optimized = path.with_suffix(".ll")
    run("opt-19", f"-passes=verify,default<{optimization}>,verify", "-S", source, "-o", optimized)
    run("llc-19", f"-mtriple={TARGET}", f"-mattr={FEATURES}", f"-{optimization}",
        "-filetype=obj", optimized, "-o", path)


def link_arguments(start, hal, output):
    return ("ld.lld-19", "--no-undefined", "--no-relax", "-T", HERE / "layout.ld", start, hal, "-o", output)


def inspect(path):
    headers = run("llvm-readelf-19", "-W", "-h", "-l", "-r", path)
    if any(not re.search(expression, headers) for expression in (
        r"Class:\s+ELF64", r"Data:.*little endian", r"Type:\s+EXEC", r"Machine:\s+RISC-V",
        r"Entry point address:\s+0x80000000", r"There are no relocations in this file",
    )):
        raise ValueError(headers)
    if re.search(r"(?m)^\s+(INTERP|DYNAMIC)\b", headers) or run("llvm-nm-19", "--undefined-only", path).strip():
        raise ValueError("unexpected dynamic loader or undefined symbol")
    loads = []
    for row in headers.splitlines():
        if not row.strip().startswith("LOAD"):
            continue
        fields = row.split()
        loads.append((int(fields[2], 16), int(fields[5], 16), "".join(fields[6:-1])))
    if len(loads) != 2 or loads[0][0] != 0x80000000 or loads[0][2] != "RE" or loads[1] != (0x80001000, 4096, "RW"):
        raise ValueError(loads)

    matches = {}
    for symbol in EXPECTED:
        assembly = run("llvm-objdump-19", "-d", f"--disassemble-symbols={symbol}", path)
        words = re.findall(r"(?m)^\s*[0-9a-f]+:\s+([0-9a-f]{8})\b", assembly)
        if len(words) != 2:
            raise ValueError((symbol, assembly))
        matches[symbol] = tuple(words)
    return {"words": matches, "load_regions": loads, "elf_sha256": sha256(path.read_bytes()).hexdigest()}


def collect(stage):
    start = stage / "start.o"
    assemble(HERE / "start.s", start)
    assembly = stage / "asm.o"
    assemble(HERE / "hal.s", assembly)
    profiles = {}
    for name, variant in (("assembly", None), ("llvm-O0", "O0"), ("llvm-O2", "O2"), ("llvm-O3", "O3")):
        obj = assembly
        if variant is not None:
            obj = stage / f"{name}.o"
            compile_ir(HERE / "hal.ll", obj, variant)
        linked = stage / f"{name}.elf"
        run(*link_arguments(start, obj, linked))
        observations = inspect(linked)
        if observations["words"] != EXPECTED:
            raise ValueError((name, observations))
        profiles[name] = observations

    native = (HERE / "hal.s").read_text()
    boundary_cases = {
        "changed-stack-pointer": (native.replace("mv a0, sp", "addi a0, sp, 16"), "read_sp"),
        "data-fence-substituted-for-translation": (native.replace("sfence.vma", "fence rw, rw"), "translation_barrier"),
    }
    controls = {}
    for name, (text, changed) in boundary_cases.items():
        mutant = stage / f"{name}.s"
        obj = mutant.with_suffix(".o")
        linked = mutant.with_suffix(".elf")
        mutant.write_text(text)
        assemble(mutant, obj)
        run(*link_arguments(start, obj, linked))
        observed = inspect(linked)["words"]
        if {key for key in EXPECTED if observed[key] != EXPECTED[key]} != {changed}:
            raise ValueError((name, observed))
        controls[name] = {"closure": "accepted", "changed_symbol": changed, "observed_words": observed[changed]}

    unresolved = stage / "hosted-symbol.s"
    unresolved.write_text(native.replace("sfence.vma", "call hosted_log"))
    imported = unresolved.with_suffix(".o")
    assemble(unresolved, imported)
    proc = subprocess.run(link_arguments(start, imported, unresolved.with_suffix(".elf")),
                          text=True, capture_output=True, timeout=30)
    if proc.returncode == 0 or "undefined symbol: hosted_log" not in proc.stderr:
        raise ValueError((proc.returncode, proc.stderr))
    controls["unresolved-hosted-symbol"] = {"closure": "rejected", "reported_symbol": "hosted_log"}
    return profiles, controls


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="rt38-hal-") as directory:
        profiles, controls = collect(Path(directory))
    evidence = {
        "target": TARGET, "instruction_extensions": FEATURES, "profiles": profiles, "controls": controls,
        "tools": {tool: run(tool, "--version").splitlines()[0]
                  for tool in ("opt-19", "llc-19", "llvm-mc-19", "ld.lld-19", "llvm-readelf-19", "llvm-objdump-19")},
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ("run.py", "hal.s", "hal.ll", "start.s", "layout.ld")},
    }
    args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n")
