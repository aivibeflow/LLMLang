"""Check exact artifact identity and scoped native observation compatibility."""

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
DOMAIN = tuple(range(256))
CHECKER = "exhaustive-u8-return-v1"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def run(root, *args):
    return subprocess.check_output(args, cwd=root, text=True, env=os.environ | {"LC_ALL": "C"})


def build(root, compiler, recipe, mode):
    directory = root / recipe["name"] / mode
    directory.mkdir(parents=True)
    source = HERE / "unit.c"
    shutil.copyfile(source, directory / "unit.c")
    flags = ["-O2", "-fPIC", "-g0", "-DSATURATE=" + ("1" if mode == "saturating" else "0")]
    run(directory, compiler, *flags, "-c", "unit.c", "-o", "unit.o")
    run(directory, "objcopy", "--dump-section", ".text=text.bin", "unit.o", "copied.o")
    run(directory, "gcc", "-shared", "-Wl,--build-id=none", "unit.o", "-o", "unit.so")
    function = ctypes.CDLL(str(directory / "unit.so")).increment
    function.argtypes = (ctypes.c_uint8,)
    function.restype = ctypes.c_uint8
    observed = [function(i) for i in DOMAIN]
    expected = [min(i + 1, 255) if mode == "saturating" else (i + 1) % 256 for i in DOMAIN]
    assert observed == expected
    plan = {"recipe": recipe, "source_sha256": sha(source.read_bytes()), "flags": flags, "semantics": mode}
    return {
        "action_key": identity(plan), "key_inputs": plan, "object_sha256": sha((directory / "unit.o").read_bytes()),
        "text_sha256": sha((directory / "text.bin").read_bytes()),
        "observation_sha256": identity(observed), "observations": observed,
    }


def bridge(source, target, inputs):
    left = [source["observations"][i] for i in inputs]
    right = [target["observations"][i] for i in inputs]
    if left != right:
        return None
    return {"origin": source["action_key"], "destination": target["action_key"],
            "scope": list(inputs), "projection": "uint8-return-only", "checker": CHECKER,
            "observations": identity(left)}


def accepts_bridge(receipt, source, target, requested):
    return receipt is not None and receipt == bridge(source, target, requested)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", type=Path, required=True)
    args = parser.parse_args()
    gcc = Path(shutil.which("gcc")).resolve()
    clang = args.clang.resolve()
    profiles = {"gcc": gcc, "clang": clang}
    results = {}
    with TemporaryDirectory(prefix="llmlang-toolchain-cache-") as scratch:
        root = Path(scratch)
        linker = Path(shutil.which("ld")).resolve()
        linkage = {"driver_sha256": sha(gcc.read_bytes()), "linker_sha256": sha(linker.read_bytes()),
                   "linker_version": run(root, linker, "--version").splitlines()[0]}
        for name, compiler in profiles.items():
            baseline = {"name": name, "compiler_sha256": sha(compiler.read_bytes()),
                        "version": run(root, compiler, "--version").splitlines()[0],
                        "target": run(root, compiler, "-dumpmachine").strip(), "linkage": linkage}
            results[name] = {mode: build(root, compiler, baseline, mode) for mode in ("wrapping", "saturating")}
    assert "14.2.0" in results["gcc"]["wrapping"]["key_inputs"]["recipe"]["version"]
    assert "23.1.1" in results["clang"]["wrapping"]["key_inputs"]["recipe"]["version"]

    source = results["gcc"]["wrapping"]
    target = results["clang"]["wrapping"]
    changed = results["clang"]["saturating"]
    full = bridge(source, target, DOMAIN)
    restricted = bridge(source, changed, DOMAIN[:-1])
    cases = {
        "cross_compiler_exact_key_matches": source["action_key"] == target["action_key"],
        "cross_compiler_exact_object_matches": source["object_sha256"] == target["object_sha256"],
        "cross_compiler_text_matches": source["text_sha256"] == target["text_sha256"],
        "exact_observation_bridge_admitted": accepts_bridge(full, source, target, DOMAIN),
        "bridge_reversed": accepts_bridge(full, target, source, DOMAIN),
        "bridge_missing": accepts_bridge(None, source, target, DOMAIN),
        "semantic_profile_change_matches_full": bridge(source, changed, DOMAIN) is not None,
        "partial_bridge_matches_its_scope": accepts_bridge(restricted, source, changed, DOMAIN[:-1]),
        "partial_bridge_reused_for_full_scope": accepts_bridge(restricted, source, changed, DOMAIN),
    }
    assert not cases["cross_compiler_exact_key_matches"] and not cases["cross_compiler_exact_object_matches"]
    assert cases["exact_observation_bridge_admitted"] and cases["partial_bridge_matches_its_scope"]
    assert not any(cases[name] for name in ("bridge_reversed", "bridge_missing",
                                           "semantic_profile_change_matches_full",
                                           "partial_bridge_reused_for_full_scope"))
    changed_rows = [i for i in DOMAIN if source["observations"][i] != changed["observations"][i]]
    assert changed_rows == [255]
    return {
        "schema": "llmlang-rt11-cross-toolchain-cache/1", "python": platform.python_version(),
        "architecture": platform.machine(), "runner_sha256": sha(Path(__file__).read_bytes()),
        "profiles": results, "comparisons": cases, "changed_semantics_inputs": changed_rows,
        "full_bridge": full, "restricted_bridge": restricted,
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
