"""Replay distinct Wasm builds against Node WASI Preview 1 and directed host controls."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent


def call(*args, cwd=None):
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True, timeout=30)
    assert not result.stderr, result.stderr
    return result.stdout.strip()


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def collect(args, work):
    direct = work / "direct.wasm"
    call("wat2wasm", HERE / "write.wat", "-o", direct)
    routes = {"direct-wat": direct}
    for mode in ("O0", "O2"):
        obj = work / f"write-{mode}.o"
        artifact = work / f"compiled-{mode}.wasm"
        call(args.clang, "--target=wasm32-unknown-unknown", "-std=c17", "-ffreestanding",
             "-fno-builtin", "-Wall", "-Wextra", "-Werror", f"-{mode}", "-c",
             HERE / "write.c", "-o", obj)
        call(args.linker, "--no-entry", "--export-memory", "--export=_initialize", "--export=emit",
             "--strip-all", obj, "-o", artifact)
        routes[f"llvm-{mode}"] = artifact
    results = {}
    expected = None
    engines = {call(node, "--version"): node for node in args.node}
    assert {version.split(".")[0] for version in engines} == {"v22", "v24"}
    for name, binary in routes.items():
        call("wasm-validate", binary)
        shape = call("wasm-objdump", "-x", binary)
        for required in ("wasi_snapshot_preview1.fd_write", '"emit"', '"memory"', '"_initialize"'):
            assert required in shape, required
        assert '"_start"' not in shape
        rows = {}
        for version, node in engines.items():
            observed = json.loads(
                call(node, "--no-warnings", HERE / "host.mjs", binary, work / "stdout")
            )
            assert observed["inputs"] == 588
            if expected is None:
                expected = observed
            assert observed == expected
            rows[version] = observed
        results[name] = {"bytes": binary.stat().st_size, "sha256": digest(binary), "engines": rows}
    return {
        "toolchain": {
            "clang": call(args.clang, "--version").splitlines()[0],
            "linker": call(args.linker, "--version"),
            "wabt": call("wat2wasm", "--version"),
        },
        "source_files": {
            name: digest(HERE / name) for name in ("write.c", "write.wat", "host.mjs", "run.py")
        },
        "routes": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--linker", default="wasm-ld")
    parser.add_argument("--node", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt13-wasi-") as directory:
        evidence = collect(args, Path(directory))
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
