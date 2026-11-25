"""Check component ownership with glibc and jemalloc process profiles."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent


def oracle():
    pairs = [(source, destination, size, alignment)
             for source in range(3) for destination in range(3)
             for size in (1, 7, 32, 128, 4095, 8192)
             for alignment in (8, 16, 64, 256, 4096)]
    checksum = 0
    for ordinal, (source, destination, size, alignment) in enumerate(pairs, 1):
        marker = (1 + size + alignment + 13 * source + 17 * destination) % 256
        checksum += ordinal * (size + marker)
    return (len(pairs), sum(source != destination for source, destination, _, _ in pairs), checksum)


def collect(args, scratch):
    environment = {key: value for key, value in os.environ.items() if key != "LD_PRELOAD"}

    def execute(command, env=environment, check=True):
        return subprocess.run(command, check=check, capture_output=True,
                              text=True, env=env, timeout=30, cwd=scratch)

    sources = [HERE / "probe.rs", HERE / "run.py",
               HERE.parents[1] / "PROTOTYPES" / "ALLOCATOR-COMPAT-01" / "probe.rs"]
    providers = {name: getattr(args, name).resolve() for name in ("glibc", "jemalloc", "mimalloc")}
    command = [args.rustc, "--edition", "2021", "-D", "warnings", sources[0]]
    profiles = []
    for name, flags in (("debug", ["-C", "opt-level=0"]), ("optimized", ["-O"])):
        binary = scratch / name
        execute([*command, *flags, "-o", binary])
        for profile in ("glibc", "jemalloc"):
            expected = providers[profile]
            env = environment if profile == "glibc" else {**environment, "LD_PRELOAD": str(expected)}
            run = execute([binary, expected, providers["mimalloc"]], env)
            observed = tuple(map(int, run.stdout.strip().split(",")))
            if observed != oracle() or run.stderr:
                raise ValueError((name, profile, observed, run.stderr))
            profiles.append(dict(build=name, system=profile, scoped="mimalloc",
                                 allocations=observed[0], refused=observed[1], checksum=observed[2]))
    compile_failure = execute([*command, "--cfg", "compile_fail_live_block", "-o", scratch / "escape"],
                              check=False)
    if compile_failure.returncode == 0 or "error[E0505]" not in compile_failure.stderr:
        raise ValueError(compile_failure.stderr)
    refusal = execute([scratch / "optimized", providers["jemalloc"], providers["mimalloc"]],
                      check=False)
    if refusal.returncode == 0 or "assertion `left == right` failed" not in refusal.stderr:
        raise ValueError(refusal.stderr)
    for provider in ("glibc", "jemalloc"):
        if providers[provider].name not in refusal.stderr:
            raise ValueError(refusal.stderr)
    return {
        "rustc": execute([args.rustc, "--version"]).stdout.strip(),
        "python": platform.python_version(),
        "platform": {"kernel": platform.release(), "machine": platform.machine()},
        "providers": {name: {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                      for name, path in providers.items()},
        "sources": {str(path.relative_to(HERE.parents[1])): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in sources},
        "profiles": profiles,
        "controls": {"early_library_retirement": "E0505",
                     "misidentified_process_provider": "runtime assertion"},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("output", "rustc", "glibc", "jemalloc", "mimalloc"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="rt25-component-allocator-") as temp:
        receipt = collect(args, Path(temp))
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
