"""Extend the exact freestanding Linux I/O contract to a separate RV64 syscall adapter."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


DIRECTORY = Path(__file__).resolve().parent
CONTRACT = DIRECTORY.parent / "LINUX-SYSCALL-ARCHITECTURES-01" / "contract.c"
PAYLOADS = (b"", b"x", b"abcd", b"abcde", b"ABCDEFGH", b"\x00\xff\x80")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def run(args, **kwargs):
    return subprocess.check_output(args, timeout=30, **kwargs)


def check(clang, linker, qemu):
    builds = {}
    with TemporaryDirectory() as folder:
        for level in (0, 2):
            artifact = Path(folder) / "rv64"
            run([clang, "--target=riscv64-linux-gnu", "-march=rv64gc", "-mabi=lp64d",
                 "-std=c17", "-Wall", "-Wextra", "-Werror", f"-O{level}", "-ffreestanding",
                 "-fno-builtin", "-fno-stack-protector", "-fno-pic", "-fno-pie", "-nostdlib",
                 "-static", f"--ld-path={linker}", "-Wl,--no-undefined,--build-id=none",
                 str(CONTRACT), str(DIRECTORY / "rv64.S"), "-o", str(artifact)])
            header = run(["readelf", "-hlWd", str(artifact)], text=True)
            assert "RISC-V" in header and "double-float ABI" in header
            assert "INTERP" not in header and "(NEEDED)" not in header
            rows = []
            for payload in PAYLOADS:
                pieces = [payload[i:i + 4] for i in range(0, len(payload), 4)]
                expected = ["BZ", *(f"{len(data)}:{data.hex()}" for data in pieces), "0:"]
                actual = run([qemu, str(artifact)], input=payload).decode().splitlines()
                assert actual == expected
                rows.append({"input_hex": payload.hex(), "trace": actual})
            builds[str(level)] = {"artifact_sha256": digest(artifact), "cases": rows}
    return {"compiler": run([clang, "--version"], text=True).splitlines()[0],
            "linker": run([linker, "--version"], text=True).splitlines()[0],
            "qemu": run([qemu, "--version"], text=True).splitlines()[0],
            "qemu_sha256": digest(Path(qemu)), "contract_sha256": digest(CONTRACT),
            "adapter_sha256": digest(DIRECTORY / "rv64.S"), "runner_sha256": digest(Path(__file__)),
            "observation": "qemu_linux_user", "builds": builds}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", required=True)
    parser.add_argument("--linker", required=True)
    parser.add_argument("--qemu", required=True)
    options = parser.parse_args()
    print(json.dumps(check(options.clang, options.linker, options.qemu), indent=2, sort_keys=True))
