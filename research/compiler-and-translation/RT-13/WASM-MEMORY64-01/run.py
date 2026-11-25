"""Check LLVM and WAT memory64 builds against a full-width view oracle."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent


def run(*command, expect_failure=False):
    result = subprocess.run(command, text=True, capture_output=True, timeout=30)
    if expect_failure:
        if result.returncode == 0 or "memory64" not in result.stderr:
            raise ValueError((command, result.returncode, result.stdout, result.stderr))
    elif result.returncode or result.stderr:
        raise ValueError((command, result.returncode, result.stdout, result.stderr))
    return result.stdout.strip()


def collect(args, scratch):
    direct = scratch / "direct-wat.wasm"
    run("wat2wasm", "--enable-memory64", HERE / "view.wat", "-o", direct)
    builds = {"direct-wat": direct}
    for name, optimize, fault in (
        ("llvm-O0", "-O0", None), ("llvm-O3", "-O3", None),
        ("llvm-narrow32", "-O3", "NARROW_32"), ("llvm-add-end", "-O3", "ADD_END"),
    ):
        artifact = scratch / f"{name}.wasm"
        obj = scratch / f"{name}.o"
        defines = [] if fault is None else [f"-D{fault}"]
        run(args.clang, "--target=wasm64-unknown-unknown", "-ffreestanding",
            "-fno-delete-null-pointer-checks", "-std=c17", "-Wall", "-Wextra", "-Werror",
            optimize, *defines, "-c", HERE / "view.c", "-o", obj)
        run("wasm-ld-19", "-mwasm64", "--no-entry", "--export=view_byte", "--export-memory",
            "--initial-memory=131072", "--max-memory=131072", "--strip-all", obj, "-o", artifact)
        builds[name] = artifact

    engines = {run(engine, "--version"): engine for engine in args.node}
    if len(engines) != 2 or {version.split(".")[0] for version in engines} != {"v22", "v24"}:
        raise ValueError("use one Node 22 engine and one Node 24 engine")
    native_expectation = {}
    results = {}
    for name, artifact in builds.items():
        run("wasm-validate", artifact, expect_failure=True)
        run("wasm-validate", "--enable-memory64", artifact)
        shape = run("wasm-objdump", "-x", artifact)
        if any(text not in shape for text in ("(i64, i64, i64) -> i32", "initial=2 max=2 i64",
                                              '-> "memory"', '-> "view_byte"')) or "Import[" in shape:
            raise ValueError(shape)
        results[name] = {
            "byte_size": artifact.stat().st_size,
            "sha256": sha256(artifact.read_bytes()).hexdigest(),
            "wabt_default": "rejected",
            "wabt_memory64_enabled": "accepted",
            "engines": {},
        }
        for version, engine in engines.items():
            observed = json.loads(run(engine, HERE / "check.mjs", artifact, "execute"))
            counts = observed["counts"]
            if counts["checked"] != 5832 or counts["bytes"] + counts["rejected"] != counts["checked"]:
                raise ValueError((version, name, counts))
            if name == "direct-wat":
                native_expectation[version] = observed.copy()
            if name in {"direct-wat", "llvm-O0", "llvm-O3"}:
                if counts["wrong"] or observed != native_expectation[version]:
                    raise ValueError((version, name, observed))
            elif counts["wrong"] <= 0:
                raise ValueError((version, name, "fault escaped"))
            if version.startswith("v22."):
                flag = "--no-experimental-wasm-memory64"
                observed["admission_with_disable_flag"] = json.loads(
                    run(engine, flag, HERE / "check.mjs", artifact, "admission")
                )["supported"]
            results[name]["engines"][version] = observed
    for build in results.values():
        profiles = [{key: value for key, value in report.items() if key != "admission_with_disable_flag"}
                    for report in build["engines"].values()]
        if profiles[0] != profiles[1]:
            raise ValueError(profiles)
    return {
        "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ("view.c", "view.wat", "check.mjs", "run.py")},
        "tools": {"clang": run(args.clang, "--version").splitlines()[0], "linker": run("wasm-ld-19", "--version"),
                  "wabt": run("wasm-validate", "--version"), "node": sorted(engines)},
        "builds": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", required=True, type=Path)
    parser.add_argument("--node", required=True, action="append", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="llmlang-memory64-") as directory:
        data = collect(args, Path(directory))
    args.output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
