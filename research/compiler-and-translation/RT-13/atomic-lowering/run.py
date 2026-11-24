#!/usr/bin/env python3
"""Compare exact LLVM atomic lowerings and replay linked RV64 fixtures."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
TARGETS = {
    "rv64": ("riscv64", "+a"),
    "rv64_zabha": ("riscv64", "+a,+zabha"),
    "aarch64": ("aarch64", "-lse"),
    "aarch64_lse": ("aarch64", "+lse"),
    "x86_64": ("x86_64", "+sse2"),
}
NO_ATOMICS = ("riscv64", "-a,-zaamo,-zalrsc")
NAMES = ("inc_monotonic", "inc_acqrel", "inc_word", "publish_fence", "read_fence")
ATOMIC_CODE = {
    "rv64": (("lr.w", "sc.w"), ("lr.w.aq", "sc.w.rl"), ("amoadd.w.aqrl",)),
    "rv64_zabha": (("amoadd.b",), ("amoadd.b.aqrl",), ("amoadd.w.aqrl",)),
    "aarch64": (("ldxrb", "stxrb"), ("ldaxrb", "stlxrb"), ("ldaxr", "stlxr")),
    "aarch64_lse": (("ldaddb",), ("ldaddalb",), ("ldaddal",)),
    "x86_64": (("lock", "xaddb"), ("lock", "xaddb"), ("lock", "xaddl")),
}


def execute(*args):
    command = list(map(str, args))
    result = subprocess.run(command, text=True, capture_output=True, timeout=25)
    if result.returncode or result.stderr:
        raise ValueError(f"Unexpected result {command}: {result.returncode} {result.stderr!r}")
    return result.stdout


def build(args, source, obj, target, level):
    arch, features = target
    execute(args.llc, f"-mtriple={arch}-unknown-none-elf", f"-mattr={features}", f"-O{level}",
            "-filetype=obj", source, "-o", obj)


def optimize(args, source, path, level):
    execute(args.opt, f"--passes=default<O{level}>,verify", "-S", source, "-o", path)
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.startswith(("; ModuleID", "source_filename"))) + "\n"


def function_ops(args, path):
    text = execute(args.objdump, "-d", "--no-show-raw-insn", path)
    labels = list(re.finditer(r"^[a-f0-9]+ <([^>]+)>:$", text, flags=re.MULTILINE))
    bodies = {}
    for index, label in enumerate(labels):
        if label[1] not in NAMES:
            continue
        end = labels[index + 1].start() if index + 1 < len(labels) else len(text)
        bodies[label[1]] = [" ".join(op.split())
                            for op in re.findall(r"^\s*[0-9a-f]+:\s*([^\n]+)", text[label.end():end], re.MULTILINE)]
    if set(bodies) != set(NAMES):
        raise ValueError(f"Incomplete target block map in {path.name}: {list(bodies)}")
    return bodies


def instruction_order(actual, expected):
    remaining = iter(actual)
    return all(any(word == operation or word.startswith(operation + " ") for word in remaining)
               for operation in expected)


def classify(args, path, name, level, *, late_release=False):
    bodies = function_ops(args, path)
    atomic = ATOMIC_CODE[name]
    if name == "aarch64" and level == 0:
        atomic = (("ldaxrb", "stlxrb"), *atomic[1:])
    for function, signature in zip(NAMES[:3], atomic, strict=True):
        if not instruction_order(bodies[function], signature):
            raise ValueError(f"Missing {signature} in {path.name} {function}")
    if name.startswith("rv64"):
        publication = ("sb", "sb", "fence rw, w") if late_release else ("sb", "fence rw, w", "sb")
        if not instruction_order(bodies["publish_fence"], publication):
            raise ValueError(f"Unexpected release-fence placement in {path.name}")
        if not instruction_order(bodies["read_fence"], ("lb", "fence r, rw", "lb")):
            raise ValueError(f"Missing target acquire fence in {path.name}")
    elif name.startswith("aarch64"):
        if not (instruction_order(bodies["publish_fence"], ("strb", "dmb ish", "strb"))
                and instruction_order(bodies["read_fence"], ("ldrb", "dmb ishld", "ldrb"))):
            raise ValueError(f"Missing target fence placement in {path.name}")
    elif any("fence" in op for key in ("publish_fence", "read_fence") for op in bodies[key]):
        raise ValueError(f"Unexpected x86 fence instruction in {path.name}")
    return bodies


def size_map(args, path):
    text = execute(args.nm, "--print-size", "--defined-only", path)
    result = {name: int(size, 16) for size, name in re.findall(r"^[\da-f]+ ([\da-f]+) T (\w+)$", text, re.MULTILINE)
              if name in NAMES}
    if set(result) != set(NAMES):
        raise ValueError(f"Missing function sizes in {path.name}")
    return result


def undefined(args, path):
    return sorted(line.split()[-1] for line in execute(args.nm, "--undefined-only", path).splitlines())


def text_digest(args, obj):
    text = obj.with_suffix(".bin")
    execute(args.objcopy, "-O", "binary", "-j", ".text", obj, text)
    return sha256(text.read_bytes()).hexdigest()


def boot(args, image, profile):
    headers = execute(args.readelf, "-W", "-h", "-l", image)
    if ("RISC-V" not in headers or not re.search(r"Entry point address:\s+0x80000000\b", headers)
            or not re.search(r"Type:\s+EXEC\b", headers)
            or re.search(r"^\s+(INTERP|DYNAMIC)\b", headers, re.MULTILINE) or undefined(args, image)):
        raise ValueError(f"Invalid freestanding image {image.name}")
    cpu = "rv64,zabha=true" if profile == "rv64_zabha" else "rv64,zabha=false"
    return execute(args.qemu, "-machine", "virt", "-cpu", cpu, "-m", "64M", "-smp", "2", "-bios", "none",
                   "-nodefaults", "-display", "none", "-monitor", "none", "-serial", "stdio", "-kernel", image)


def controls(args, work, original, boot_obj, builds):
    shifted = original.replace("  fence release\n  store atomic i8 1, ptr %flag monotonic, align 1",
                               "  store atomic i8 1, ptr %flag monotonic, align 1\n  fence release")
    wrong_byte = original.replace("  %previous = atomicrmw add ptr %counter, i8 %delta acq_rel",
                                  "  %wrong = getelementptr i8, ptr %counter, i64 1\n"
                                  "  %previous = atomicrmw add ptr %wrong, i8 %delta acq_rel")
    if shifted == original or wrong_byte == original:
        raise ValueError("A named mutant did not change its LLVM source")
    result = {}
    for name, source in (("release_after_flag", shifted), ("wrong_byte", wrong_byte)):
        ir, optimized = work / f"{name}.ll", work / f"{name}-opt.ll"
        ir.write_text(source, encoding="utf-8")
        normalized = optimize(args, ir, optimized, 3)
        result[name] = {"normalized_ir_sha256": sha256(normalized.encode()).hexdigest()}
        for profile in ("rv64", "x86_64") if name == "release_after_flag" else ("rv64", "rv64_zabha"):
            obj = work / f"{name}-{profile}.o"
            build(args, optimized, obj, TARGETS[profile], level=3)
            digest = text_digest(args, obj)
            matched = digest == builds[f"{profile}_O3"]["text_sha256"]
            if name == "release_after_flag":
                if matched != (profile == "x86_64"):
                    raise ValueError(f"Unexpected target sensitivity to a source fence move under {profile}")
                result[name][profile] = {"matches_reference_text": matched, "text_sha256": digest,
                                         "publish_instructions": classify(args, obj, profile, 3, late_release=True)[
                                             "publish_fence"]}
                continue
            image = obj.with_suffix(".elf")
            execute(args.lld, "--no-relax", "-T", HERE / "layout.ld", "-o", image, boot_obj, obj)
            uart = boot(args, image, profile)
            if uart != "X":
                raise ValueError(f"Wrong-byte control was not detected in {profile}: {uart!r}")
            result[name][profile] = {"uart": uart, "elf_sha256": sha256(image.read_bytes()).hexdigest()}
    return result


def replay(args):
    source = HERE / "operations.ll"
    with TemporaryDirectory(prefix="llmlang-rv64-atomic-lowering-") as directory:
        work = Path(directory)
        boot_obj = work / "boot.o"
        execute(args.mc, "-triple", "riscv64-unknown-none-elf", "-mattr=+a,+zicsr,+zifencei",
                "-filetype=obj", HERE / "boot.s", "-o", boot_obj)
        levels = {}
        builds = {}
        for level in (0, 3):
            ir = work / f"optimized-{level}.ll"
            normalized = optimize(args, source, ir, level)
            signatures = (r"atomicrmw add ptr %counter, i8 %delta monotonic",
                          r"atomicrmw add ptr %counter, i8 %delta acq_rel",
                          r"atomicrmw add ptr %counter, i32 %delta acq_rel",
                          r"fence release\s+store atomic i8 1",
                          r"fence acquire\s+%\w+ = load atomic i8")
            if any(not re.search(signature, normalized) for signature in signatures):
                raise ValueError(f"Unexpected optimized LLVM ordering or width at O{level}")
            levels[f"O{level}"] = sha256(normalized.encode()).hexdigest()
            for profile, target in TARGETS.items():
                name = f"{profile}_O{level}"
                obj = work / f"{name}.o"
                build(args, ir, obj, target, level)
                if undefined(args, obj):
                    raise ValueError(f"Unexpected runtime helper in {name}")
                body = classify(args, obj, profile, level)
                entry = {"text_sha256": text_digest(args, obj), "function_bytes": size_map(args, obj),
                         "instructions": body}
                if profile.startswith("rv64"):
                    image = obj.with_suffix(".elf")
                    execute(args.lld, "--no-relax", "-T", HERE / "layout.ld", "-o", image, boot_obj, obj)
                    classify(args, image, profile, level)
                    uart = boot(args, image, profile)
                    if uart != "R!":
                        raise ValueError(f"Unexpected QEMU atomic trace for {name}: {uart!r}")
                    entry.update(elf_sha256=sha256(image.read_bytes()).hexdigest(), uart=uart)
                builds[name] = entry
        disabled = work / "no-atomics.o"
        build(args, ir, disabled, NO_ATOMICS, 3)
        imports = undefined(args, disabled)
        if imports != ["__atomic_fetch_add_1", "__atomic_fetch_add_4", "__atomic_load_1", "__atomic_store_1"]:
            raise ValueError(f"Unexpected RV64 no-A runtime dependencies: {imports}")
        mutations = controls(args, work, source.read_text(), boot_obj, builds)

    return {"schema": "llmlang-rt13-atomic-lowering-v1", "native_machine": "rv64-virt", "native_harts": 2,
            "tools": {name: execute(getattr(args, name), "--version").splitlines()[0].strip()
                      for name in ("opt", "llc", "lld", "objdump", "qemu")},
            "inputs_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                              for name in ("operations.ll", "boot.s", "layout.ld", "run.py")},
            "normalized_ir_sha256": levels, "profiles": builds,
            "rv64_no_a_undefined": imports, "controls": mutations}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, command in {
        "opt": "opt-19", "llc": "llc-19", "mc": "llvm-mc-19", "lld": "ld.lld-19",
        "readelf": "llvm-readelf-19", "nm": "llvm-nm-19", "objdump": "llvm-objdump-19",
        "objcopy": "llvm-objcopy-19", "qemu": "qemu-system-riscv64",
    }.items():
        parser.add_argument(f"--{name}", default=command)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(replay(args), indent=2) + "\n", encoding="utf-8")
