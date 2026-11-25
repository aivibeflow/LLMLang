"""Rebuild the four native binary64 studies from their exact Git source."""

import hashlib
import io
import json
import os
import platform
import subprocess
import tarfile
import tempfile
from pathlib import Path

BASELINE = "756d582cc0c8d4a084fbd9faffcaff9d9c8ece47"
FIXTURES = (
    "research/semantic-representation/RT-05/CROSS-RUNTIME-F64-01",
    "research/semantic-representation/RT-05/NATIVE-F64-MINMAX-01",
    "research/semantic-representation/RT-05/F64-I64-CONVERSION-01",
    "research/compiler-and-translation/RT-13/BINARY64-CONTRACTION-01",
)


def version(*args):
    return subprocess.check_output(args, text=True).strip().splitlines()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    archive = subprocess.check_output(["git", "archive", BASELINE, *FIXTURES])
    environment = os.environ | {"LC_ALL": "C", "PYTHONHASHSEED": "1"}
    replays = {}
    with tempfile.TemporaryDirectory(prefix="llmlang-binary64-replay-") as temporary:
        root = Path(temporary)
        with tarfile.open(fileobj=io.BytesIO(archive)) as source:
            source.extractall(root, filter="data")
        for path in FIXTURES:
            runner = root / path / "run.py"
            command = ["python3", "-B", str(runner)]
            if path.endswith("BINARY64-CONTRACTION-01"):
                output = root / "observed.json"
                subprocess.run(command + ["--output", str(output)], env=environment,
                               check=True, timeout=120)
                observed = output.read_bytes()
            else:
                observed = subprocess.check_output(command, env=environment, timeout=120)
            expected = (root / path / "evidence.json").read_bytes()
            if observed != expected:
                raise ValueError(f"{path}: observed {digest(observed)}, archive {digest(expected)}")
            replays[path] = {
                "runner_sha256": digest(runner.read_bytes()),
                "archive_sha256": digest(expected),
                "replay_sha256": digest(observed),
                "bytes": len(observed),
                "byte_equal": True,
            }
    print(json.dumps({
        "baseline": BASELINE,
        "python": platform.python_version(),
        "git": version("git", "--version")[0],
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "rustc": version("rustc", "--version", "--verbose"),
        "node": version("node", "--version")[0],
        "v8": version("node", "-p", "process.versions.v8")[0],
        "gcc": version("gcc", "--version")[0],
        "binutils": version("objdump", "--version")[0],
        "glibc": version("ldd", "--version")[0],
        "java": version("java", "--version"),
        "locale": environment["LC_ALL"],
        "python_hash_seed": environment["PYTHONHASHSEED"],
        "replays": replays,
    }, indent=2))


if __name__ == "__main__":
    main()
