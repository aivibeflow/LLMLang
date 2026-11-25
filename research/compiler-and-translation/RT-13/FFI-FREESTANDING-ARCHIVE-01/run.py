"""Build and replay an explicit static FFI dependency on ARM and RISC-V guests."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
SOURCES = ("ffi.h", "provider.c", "support.c", "consumer.c", "arm.S", "riscv.S", "arm.ld", "riscv.ld", "xtensa.s", "memory.c")
PROFILES = {
    "cortex-m3": ("thumbv7m-none-eabi", ("-mcpu=cortex-m3",), "arm", 40, 1, "lm3s6965evb"),
    "cortex-m4f": ("thumbv7em-none-eabihf", ("-mcpu=cortex-m4", "-mfpu=fpv4-sp-d16",
                                         "-mfloat-abi=hard"), "arm", 40, 1, "mps2-an386"),
    "rv32": ("riscv32-unknown-none-elf", ("-march=rv32imac", "-mabi=ilp32"),
             "riscv", 243, 1, "virt"),
    "rv64": ("riscv64-unknown-none-elf", ("-march=rv64imac", "-mabi=lp64", "-mcmodel=medany"),
             "riscv", 243, 2, "virt"),
}


def command(*args, cwd=None, checked=True):
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=checked, timeout=25)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def oracle(mutated):
    state = 0
    events = []
    for request in (0, 1, 5, 6, 3, 9, 2):
        if request > 5:
            status, trace = 1, 1
        else:
            state += 2 * request + 1
            status, trace = 0, 1 if mutated else 6
        events.append(f"{status}{chr(65 + state)}{trace}")
    return "".join(events) + "!"


def signature(path):
    data = path.read_bytes()
    assert data[:4] == b"\x7fELF" and data[5] == 1
    return struct.unpack_from("<H", data, 18)[0], data[4]


def boot(args, name, family, board, elf):
    if family == "arm":
        processor = "cortex-m3" if name == "cortex-m3" else "cortex-m4"
        argv = [args.qemu_arm, "-machine", board, "-cpu", processor, "-nodefaults", "-display", "none",
                "-monitor", "none", "-semihosting-config", "enable=on,target=native,chardev=observed",
                "-chardev", "stdio,id=observed"]
    else:
        argv = [getattr(args, f"qemu_{name}"), "-machine", "virt", "-m", "64M", "-smp", "1",
                "-bios", "none", "-nodefaults", "-display", "none", "-monitor", "none",
                "-serial", "stdio"]
    if args.qemu_data:
        argv.extend(["-L", args.qemu_data])
    result = command(*argv, "-kernel", elf, checked=False)
    assert result.returncode == 0, (name, result.stderr)
    known_board_messages = {
        "Timer with period zero, disabling",
        "qemu-system-arm: warning: nic stellaris_enet.0 has no peer",
        "qemu-system-arm: warning: nic lan9118.0 has no peer",
    }
    assert set(result.stderr.splitlines()) <= known_board_messages, result.stderr
    return result.stdout



def xtensa_profiles(args, work):
    root = work / "xtensa"
    root.mkdir()
    candidate = root / "generic-leaf.o"
    command(args.mc, "-triple=xtensa-unknown-none-elf", "-filetype=obj",
            HERE / "xtensa.s", "-o", candidate)
    assert signature(candidate) == (94, 1)
    unavailable = command(args.clang, "--target=xtensa-none-elf", "-ffreestanding",
                          "-c", HERE / "provider.c", "-o", root / "generic-provider.o", checked=False)
    assert unavailable.returncode and "unknown target triple" in unavailable.stderr

    compiler = args.xtensa_bin / "xtensa-esp32-elf-gcc"
    linker = args.xtensa_bin / "xtensa-esp32-elf-ld"
    objdump = args.xtensa_bin / "xtensa-esp32-elf-objdump"
    results = {}
    for abi, calls in (("call0", ("call0", "callx0")), ("windowed", ("call8", "callx8"))):
        directory = root / abi
        directory.mkdir()
        objects = {}
        for name in ("provider", "consumer", "support"):
            obj = directory / f"{name}.o"
            command(compiler, f"-mabi={abi}", "-ffreestanding", "-fno-builtin", "-O2",
                    "-Wall", "-Wextra", "-Werror", "-c", HERE / f"{name}.c", "-o", obj)
            assert signature(obj) == (94, 1)
            objects[name] = digest(obj)
        command(args.ar, "rcsD", "libprovider.a", "provider.o", cwd=directory)
        command(linker, "-r", "consumer.o", "libprovider.a", "support.o", "-o", "interchange.o",
                cwd=directory)
        composite = directory / "interchange.o"
        assert signature(composite) == (94, 1)
        undefined = command(args.nm, "--undefined-only", composite).stdout.split()
        assert undefined == ["U", "marker", "U", "memcpy"], (abi, undefined)
        memory = directory / "memory.o"
        command(compiler, f"-mabi={abi}", "-ffreestanding", "-fno-builtin",
                "-fno-tree-loop-distribute-patterns", "-O2", "-c", HERE / "memory.c", "-o", memory)
        assert not command(args.nm, "--undefined-only", memory).stdout.strip()
        supported = directory / "supported.o"
        command(linker, "-r", composite, memory, "-o", supported)
        assert command(args.nm, "--undefined-only", supported).stdout.split() == ["U", "marker"]
        trace = command(objdump, "-d", supported).stdout
        assert all(re.search(r"\b" + name + r"\b", trace) for name in calls), (abi, trace[:1000])
        results[abi] = {
            "object_sha256": objects, "archive_sha256": digest(directory / "libprovider.a"),
            "linked_object_sha256": digest(composite), "called_register_groups": calls,
            "explicit_memory_support": digest(memory),
            "supported_object_sha256": digest(supported),
            "remaining_startup_symbol": "marker",
        }
    wrong = command(
        linker, "-r", root / "call0/consumer.o", root / "windowed/libprovider.a",
        root / "windowed/support.o", "-o", root / "mixed.o", checked=False,
    )
    assert wrong.returncode == 0
    combined = root / "mixed.o"
    mixed_calls = command(objdump, "-d", combined).stdout
    assert all(re.search(r"\b" + name + r"\b", mixed_calls) for name in ("call0", "callx8"))
    return {
        "llvm_generic_assembly_object_sha256": digest(candidate),
        "llvm_c_frontend_for_generic_target": "refused",
        "vendor_toolchain": command(compiler, "--version").stdout.splitlines()[0],
        "vendor_object_interchange": results,
        "mixed_vendor_call_conventions": {
            "link": "accepted", "mixed_object_sha256": digest(combined),
            "profile_gate": "refused",
        },
    }


def collect(args, work):
    artifacts = {}
    for name, (target, target_options, family, machine, width, board) in PROFILES.items():
        root = work / name
        root.mkdir()
        flags = [args.clang, f"--target={target}", *target_options, "-ffreestanding", "-fno-builtin",
                 "-fno-unwind-tables", "-fno-asynchronous-unwind-tables", "-O2"]
        opt_boot = ["-DENABLE_FPU"] if name == "cortex-m4f" else []
        for input_path, object_name, options in (
            ("consumer.c", "consumer.o", []), ("support.c", "support.o", []),
            ("provider.c", "provider.o", []), ("provider.c", "omitted.o", ["-DOMIT_EVENT"]),
            (f"{family}.S", "boot.o", opt_boot),
            (f"{family}.S", "boot-no-zero.o", [*opt_boot, "-DOMIT_ZERO"]),
        ):
            command(*flags, *options, "-c", HERE / input_path, "-o", object_name, cwd=root)
            assert signature(root / object_name) == (machine, width)
        for obj, archive in (("provider", "libprovider"), ("omitted", "libomitted"), ("support", "libsupport")):
            command(args.ar, "rcsD", f"{archive}.a", f"{obj}.o", cwd=root)
        link = [args.linker, "--no-undefined", "--no-relax", "-T", HERE / f"{family}.ld"]
        rejected = command(*link, "boot.o", "consumer.o", "libprovider.a", "-o", "missing",
                           cwd=root, checked=False)
        assert rejected.returncode and "checked_support" in rejected.stderr
        rows = {}
        for route, startup, library, expected in (
            ("preserving", "boot.o", "libprovider.a", oracle(False)),
            ("omitted_event", "boot.o", "libomitted.a", oracle(True)),
            ("omitted_startup_zero", "boot-no-zero.o", "libprovider.a", "X!"),
        ):
            elf = root / f"{route}.elf"
            command(*link, startup, "consumer.o", library, "libsupport.a", "-o", elf, cwd=root)
            assert signature(elf) == (machine, width)
            metadata = command(args.readelf, "-lW", "-rW", elf).stdout
            assert not re.search(r"(?m)^\s+(INTERP|DYNAMIC)", metadata)
            assert "There are no relocations" in metadata
            assert not command(args.nm, "--undefined-only", elf).stdout.strip()
            trace = boot(args, name, family, board, elf)
            assert trace == expected, (name, route, trace, expected)
            rows[route] = {"elf_sha256": digest(elf), "trace": trace}
        fpu = command(args.readelf, "-A", root / "provider.o").stdout
        assert ("Tag_ABI_VFP_args: VFP registers" in fpu) == (name == "cortex-m4f")
        artifacts[name] = {
            "target": target, "machine": machine, "elf_class": width,
            "architecture_options": target_options, "actual_machine": board,
            "support_archive_sha256": digest(root / "libsupport.a"),
            "provider_archive_sha256": digest(root / "libprovider.a"),
            "missing_support": "link-refused", "profiles": rows,
        }

    xtensa_results = xtensa_profiles(args, work)
    return {
        "profiles": artifacts, "xtensa_object_only": xtensa_results,
        "sources": {name: digest(HERE / name) for name in ("run.py", *SOURCES)},
        "tools": {
            name: command(getattr(args, name), "--version").stdout.splitlines()[0]
            for name in ("clang", "linker", "qemu_arm", "qemu_rv32", "qemu_rv64")
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, binary in (
        ("clang", "clang"), ("linker", "ld.lld"), ("ar", "llvm-ar"),
        ("readelf", "readelf"), ("nm", "llvm-nm"), ("mc", "llvm-mc"),
        ("qemu-arm", "qemu-system-arm"), ("qemu-rv32", "qemu-system-riscv32"),
        ("qemu-rv64", "qemu-system-riscv64"),
    ):
        parser.add_argument(f"--{name}", default=binary)
    parser.add_argument("--qemu-data", type=Path)
    parser.add_argument("--xtensa-bin", required=True, type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt13-ffi-freestanding-") as directory:
        evidence = collect(args, Path(directory))
    args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
