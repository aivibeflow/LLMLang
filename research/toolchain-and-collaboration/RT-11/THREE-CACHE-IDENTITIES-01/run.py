"""Compare exact semantic, action, and artifact identities for short C builds."""

import ctypes
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

BASELINE = "017d2e73e32b3fe050ff62f41d145d871781c21e"
ROOT = Path(__file__).resolve().parents[4]
MODES = {
    "full-optimized": (1, "all-unsigned", ("-O2",)),
    "full-higher-optimization": (1, "all-unsigned", ("-O3",)),
    "full-debug": (1, "all-unsigned", ("-O2", "-g")),
    "restricted-optimized": (1, "byte-inputs", ("-O2",)),
    "changed-body": (2, "all-unsigned", ("-O2",)),
}
INPUTS = (0, 1, 31, 255)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(domain, payload):
    wire = json.dumps([domain, payload], sort_keys=True, separators=(",", ":")).encode()
    return sha(wire)


def archived():
    paths = (
        "research/toolchain-and-collaboration/RT-11/CROSS-TOOLCHAIN-CACHE-01/evidence.json",
        "research/compiler-and-translation/RT-13/COMPILE-ACTION-INPUTS-01/evidence.json",
    )
    return {path: sha(subprocess.check_output(["git", "show", f"{BASELINE}:{path}"], cwd=ROOT))
            for path in paths}


def execute(args, work, environment):
    return subprocess.check_output(args, cwd=work, env=environment, timeout=30)


def build_all():
    compiler = Path(shutil.which("gcc")).resolve(strict=True)
    engine = {"sha256": sha(compiler.read_bytes()), "version": subprocess.check_output(
        [compiler, "--version"], text=True).splitlines()[0], "target": subprocess.check_output(
        [compiler, "-dumpmachine"], text=True).strip()}
    rows = {}
    with tempfile.TemporaryDirectory(prefix="llmlang-identity-") as temporary:
        work = Path(temporary)
        environment = os.environ | {"LC_ALL": "C", "SOURCE_DATE_EPOCH": "0"}
        for name, (increment, contract, flags) in MODES.items():
            body = f"unsigned entry(unsigned value) {{ return value + {increment}u; }}\n".encode()
            (work / "input.c").write_bytes(body)
            options = ("-c", "-fPIC", "-fdebug-prefix-map=" + str(work) + "=/fixture", *flags)
            declaration = {"increment": increment, "contract_scope": contract}
            compile_manifest = {"input_sha256": sha(body), "engine": engine, "flags": flags,
                                "recipe": "C PIC object with fixed source name and debug virtual root"}
            execute([compiler, *options, "input.c", "-o", "output.o"], work, environment)
            library = work / (name + ".so")
            execute([compiler, "-shared", "output.o", "-o", library], work, environment)
            entry = ctypes.CDLL(str(library)).entry
            entry.argtypes = (ctypes.c_uint,)
            entry.restype = ctypes.c_uint
            observed = [entry(value) for value in INPUTS]
            assert observed == [value + increment for value in INPUTS]
            rows[name] = {
                "declaration": declaration, "inputs": compile_manifest,
                "subject_hash": identity("semantic-subject/1", declaration),
                "action_key": identity("c-compile/1", compile_manifest),
                "artifact_sha256": sha((work / "output.o").read_bytes()),
                "observation": observed,
            }
    return engine, rows


def main():
    engine, rows = build_all()
    original = rows["full-optimized"]
    comparisons = {}
    for name, row in rows.items():
        comparisons[name] = {field: row[field] == original[field]
                             for field in ("subject_hash", "action_key", "artifact_sha256", "observation")}
    assert comparisons["full-higher-optimization"] == {
        "subject_hash": True, "action_key": False, "artifact_sha256": True, "observation": True,
    }
    assert comparisons["full-debug"] == {
        "subject_hash": True, "action_key": False, "artifact_sha256": False, "observation": True,
    }
    assert comparisons["restricted-optimized"] == {
        "subject_hash": False, "action_key": True, "artifact_sha256": True, "observation": True,
    }
    assert not any(comparisons["changed-body"].values())
    def incomplete_key(row):
        return identity("c-compile/1", {name: value for name, value in row["inputs"].items() if name != "flags"})

    debug = rows["full-debug"]
    assert incomplete_key(original) == incomplete_key(debug)
    assert original["artifact_sha256"] != debug["artifact_sha256"]
    tools = {name: subprocess.check_output([name, "--version"], text=True).splitlines()[0]
             for name in ("as", "ld")}
    print(json.dumps({
        "baseline": BASELINE, "python": platform.python_version(), "gcc": engine,
        "runner_sha256": sha(Path(__file__).read_bytes()), "archive_hashes": archived(),
        "native_tools": tools, "host": platform.platform(),
        "flags_omission_control": {"same_incomplete_key": True, "same_artifact": False},
        "inputs": INPUTS, "builds": rows, "comparisons_with_original": comparisons,
    }, indent=2))


if __name__ == "__main__":
    main()
