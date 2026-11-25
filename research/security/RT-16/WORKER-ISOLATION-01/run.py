"""Compare independent build-worker launch controls using only synthetic inputs."""

import argparse
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
FIXTURE_ONLY = "deterministic-fixture-private-value"


def run(arguments, work, **kwargs):
    return subprocess.run(arguments, cwd=work, check=True, capture_output=True,
                          text=True, timeout=30, **kwargs).stdout


def files(work):
    for folder, byte in (("public", b"public input"), ("private", b"synthetic input")):
        directory = work / folder
        directory.mkdir()
        directory.joinpath("input").write_bytes(byte)


def observe(program, work, keep_env, keep_fd, restricted):
    environment = {"LC_ALL": "C", "LLMLANG_FIXTURE_PUBLIC": "declared-public-input"}
    if keep_env:
        environment["LLMLANG_FIXTURE_PRIVATE"] = FIXTURE_ONLY
    public_fd = os.open(work / "public" / "input", os.O_RDONLY)
    private_fd = os.open(work / "private" / "input", os.O_RDONLY)
    try:
        inherited = (public_fd, private_fd) if keep_fd else (public_fd,)
        report = run([str(program), "restricted" if restricted else "plain",
                      str(public_fd), str(private_fd)], work, env=environment,
                     close_fds=True, pass_fds=inherited)
    finally:
        os.close(private_fd)
        os.close(public_fd)
    if FIXTURE_ONLY in report:
        raise ValueError("A diagnostic printed input data")
    return {key: bool(int(value)) for key, value in
            (line.split("=", 1) for line in report.splitlines())}


def assess(cc, work):
    files(work)
    profiles = {}
    matrix = {}
    for level in (0, 2):
        probe = work / f"probe-O{level}"
        run([cc, "-std=c17", "-Wall", "-Wextra", "-Werror",
             f"-O{level}", str(HERE / "probe.c"), "-o", str(probe)], work)
        abi, abi_errno = map(int, run([str(probe), "--version"], work).split())
        profiles[f"O{level}"] = {"binary_sha256": sha256(probe.read_bytes()).hexdigest(),
                                  "landlock_abi_query": [abi, abi_errno], "repetitions": 3}
        for inherited_env, inherited_fd, restricted in product((False, True), repeat=3):
            name = f"env={inherited_env},fd={inherited_fd},seccomp={restricted}"
            expected = {
                "public_env": True, "fixture_private_env": inherited_env,
                "public_fd": True, "fixture_private_fd": inherited_fd,
                "public_path_read": not restricted,
                "fixture_private_path_read": not restricted,
                "public_path_write": not restricted,
            }
            for repeat in range(3):
                actual = observe(probe, work, inherited_env, inherited_fd, restricted)
                if actual != expected:
                    raise AssertionError((level, name, repeat, actual, expected))
            matrix[name] = expected
    return {
        "compiler": run([cc, "--version"], work).splitlines()[0],
        "kernel": platform.release(),
        "machine": platform.machine(),
        "configurations": len(matrix),
        "native_launches": len(matrix) * len(profiles) * 3,
        "native_fields_checked": sum(len(values) for values in matrix.values()) * len(profiles) * 3,
        "profiles": profiles,
        "presence_observations": matrix,
        "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ("probe.c", "run.py")},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-worker-isolation-") as temp:
        print(json.dumps(assess(args.cc, Path(temp)), indent=2))
