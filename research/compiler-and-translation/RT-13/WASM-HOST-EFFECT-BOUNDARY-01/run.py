"""Compare LLVM and direct Wasm under fixed host imports and boundary inputs."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent


def run(arguments):
    return subprocess.check_output(arguments, cwd=HERE, text=True, timeout=30)


def study(options):
    node = options.node or ["node"]
    engines = {run([executable, "--version"]).strip(): executable for executable in node}
    assert len(engines) == len(node)
    builds = {}
    with TemporaryDirectory() as temporary:
        work = Path(temporary)
        import_symbols = work / "allowed-undefined.txt"
        import_symbols.write_text("commit\n")
        for level in (0, 3):
            obj = work / f"llvm-O{level}.o"
            module = work / f"llvm-O{level}.wasm"
            run([options.clang, "--target=wasm32-unknown-unknown", "-std=c17", "-Wall", "-Wextra",
                 "-Werror", f"-O{level}", "-ffreestanding", "-c", "invoke.c", "-o", obj])
            run([options.linker, "--no-entry", "--export=invoke", "--strip-all",
                 f"--allow-undefined-file={import_symbols}", obj, "-o", module])
            builds[f"llvm-O{level}"] = module
        module = work / "direct.wasm"
        run([options.wat, "invoke.wat", "-o", module])
        builds["direct"] = module
        results = {}
        for name, artifact in builds.items():
            results[name] = {
                "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                "host_observations": {
                    engine: json.loads(run([executable, "runner.mjs", artifact]))
                    for engine, executable in engines.items()
                },
            }
    reference = next(iter(results["direct"]["host_observations"].values()))
    assert all(observation == reference for result in results.values()
               for observation in result["host_observations"].values())
    return {
        "python": platform.python_version(),
        "clang": run([options.clang, "--version"]).splitlines()[0],
        "linker": run([options.linker, "--version"]).splitlines()[0],
        "node": sorted(engines),
        "wat2wasm": run([options.wat, "--version"]).strip(),
        "builds": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--linker", default="wasm-ld-19")
    parser.add_argument("--wat", default="wat2wasm")
    parser.add_argument("--node", action="append")
    print(json.dumps(study(parser.parse_args()), indent=2, sort_keys=True))
