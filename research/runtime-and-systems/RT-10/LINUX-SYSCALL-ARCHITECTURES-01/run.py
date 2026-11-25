"""Run one freestanding Linux I/O contract with two separate syscall ABIs."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory


TARGETS = {
    "x86_64": ("x86_64-linux-gnu", "Advanced Micro Devices X86-64"),
    "aarch64": ("aarch64-linux-gnu", "AArch64"),
}
PAYLOADS = (b"", b"x", b"abcd", b"abcde", b"ABCDEFGH", b"\x00\xff\x80")


def run(args, **overrides):
    return subprocess.check_output(args, timeout=30, **overrides)


def study(options):
    folder = Path(__file__).resolve().parent
    assert platform.machine() == "x86_64"
    results = {}
    with TemporaryDirectory() as temporary:
        for architecture, (triple, elf_machine) in TARGETS.items():
            results[architecture] = {}
            for level in (0, 2):
                artifact = Path(temporary) / f"{architecture}-O{level}"
                run([
                    options.clang, f"--target={triple}", "-std=c17", "-Wall", "-Wextra", "-Werror",
                    f"-O{level}", "-ffreestanding", "-fno-builtin", "-fno-stack-protector",
                    "-fno-pic", "-fno-pie", "-nostdlib", "-static", "-fuse-ld=lld",
                    "-Wl,--no-undefined,--build-id=none", str(folder / "contract.c"),
                    str(folder / f"{architecture}.S"), "-o", str(artifact),
                ])
                header = run(["readelf", "-hW", str(artifact)], text=True)
                assert any(line.strip().startswith("Machine:") and line.strip().endswith(elf_machine)
                           for line in header.splitlines())
                dynamic = run(["readelf", "-lWd", str(artifact)], text=True)
                assert "INTERP" not in dynamic and "(NEEDED)" not in dynamic
                command = [str(artifact)] if architecture == "x86_64" else [options.qemu, str(artifact)]
                cases = []
                for payload in PAYLOADS:
                    expected = ["BZ"] + [
                        f"{len(piece)}:{piece.hex()}" for offset in range(0, len(payload), 4)
                        for piece in (payload[offset:offset + 4],)
                    ] + ["0:"]
                    observation = run(command, input=payload).decode().splitlines()
                    assert observation == expected, (architecture, level, payload, observation)
                    cases.append({"input_hex": payload.hex(), "trace": observation})
                results[architecture][str(level)] = {
                    "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                    "observation": "native" if architecture == "x86_64" else "qemu_linux_user",
                    "cases": cases,
                }
    return {
        "python": platform.python_version(),
        "kernel": platform.release(),
        "clang": run([options.clang, "--version"], text=True).splitlines()[0],
        "qemu": run([options.qemu, "--version"], text=True).splitlines()[0],
        "qemu_sha256": hashlib.sha256(Path(options.qemu).read_bytes()).hexdigest(),
        "builds": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--qemu", required=True)
    print(json.dumps(study(parser.parse_args()), indent=2, sort_keys=True))
