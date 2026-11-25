#!/usr/bin/env python3
"""Reproduce the pinned RT-13 FFI evidence cohort outside the working tree."""
import argparse
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile


BASE = "3281d6863c2abd2f8eb3bdb05982bd3439d3c481"
RT = "research/compiler-and-translation/RT-13"


def invoke(argv, cwd, env, timeout=140):
    result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=timeout)
    assert result.returncode == 0, (argv, result.stdout.decode(errors="replace"),
                                     result.stderr.decode(errors="replace"))
    return result.stdout


def capture(repo, scratch, env):
    payload = invoke(["git", "archive", BASE, RT], repo, env)
    with tarfile.open(fileobj=BytesIO(payload), mode="r:") as source:
        source.extractall(scratch, filter="data")


def replay(repo, scratch, folder, filename, options, env):
    source = scratch / RT / folder
    actual = scratch / "result.json"
    invoke([sys.executable, "-B", source / "run.py", *options, actual], scratch, env)
    regenerated = actual.read_bytes()
    actual.unlink()
    expected = (source / filename).read_bytes()
    assert regenerated == expected, (folder, sha256(regenerated).hexdigest(), sha256(expected).hexdigest())
    contents = {
        name: invoke(["git", "rev-parse", f"{BASE}:{RT}/{folder}/{name}"], repo, env).decode().strip()
        for name in ("run.py", filename)
    }
    return json.loads(regenerated), {"git_blobs": contents, "sha256": sha256(regenerated).hexdigest()}


def comparison(ledgers):
    summaries = {}
    loader = ledgers["loader"]["summary"]
    assert (loader["dynamic_processes"], loader["exact_later_binding"],
            loader["semantic_match_wrong_identity"]) == (126, 42, 28)
    summaries["loader"] = {"processes": 126, "equal_output_wrong_provider": 28}
    raw = ledgers["header"]
    assert len(raw["declarations"]) == 19 and sum(raw["signature_only_wrong_pairs"].values()) == 16
    assert len(raw["behaviors"]["sqlite"]) == 12 and len(raw["refusals"]) == 3
    summaries["header"] = {"imports": 19, "equal_signature_distinguishers": 16}
    assert ledgers["callback"]["summary"] == {"completed-upcall": 432, "typed-error": 72}
    assert ledgers["managed"]["upcall_totals"] == {"returned": 576, "typed_error": 96}
    summaries["callbacks"] = {"c_cpython_rust": 504, "go_jvm": 672}
    assert ledgers["managed"]["controls"]["go-no-native-stdout-flush"] == {"exit": 0, "stdout_bytes": 0}
    aggregate = ledgers["aggregate"]["profiles"]
    assert all(len(profile["routes"]["wrong"]["mixed_mismatch"]) == 24 for profile in aggregate.values())
    assert sum(profile["routes"]["assembly"]["matched"] + profile["routes"]["c"]["matched"]
               for profile in aggregate.values()) == 288
    stretch = ledgers["variadic"]["profiles"]
    counts = [sum(len(profile["routes"][key]["mismatching_indices"]) for profile in stretch.values())
              for key in ("wrong-floating-register", "bypassed-float-conversion")]
    assert counts == [240, 90] and len(stretch) == 10
    summaries["abi"] = {"positive_aggregate_cases": 288, "wrong_vararg_register": 240,
                        "missing_source_promotion": 90}
    packages = ledgers["package"]
    assert packages["reproducible_builds"] == 12 and packages["fresh_connection_reuses"] == 6
    assert packages["false_hits_by_key"] == {"build-host": 5, "triple": 2}
    assert packages["cache_refusal_controls"]["same-abi-different-provider-recipe"] == "receipt-mismatch"
    summaries["packages"] = {"exact_rebuilt_packages": 12, "reuse_after_reconnect": 6}
    clauses = ledgers["conditional"]
    assert clauses["native_compared"] == 1440 and len(clauses["control_outcomes"]) == 15
    summaries["conditional_receipt"] = {"native_observations": 1440, "controls": 15}
    return summaries


def main():
    parser = argparse.ArgumentParser()
    flags = ("rustc", "lean", "clang", "clang-libdir", "sqlite-include", "sqlite-library",
             "crypto-library", "libc-library", "lld", "qemu-aarch64", "qemu-riscv64", "go",
             "go-cache", "out")
    for flag in flags:
        parser.add_argument(f"--{flag}", type=lambda value: Path(value).absolute(),
                            required=flag not in {"clang-libdir", "go-cache"})
    args = parser.parse_args()
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update({"LC_ALL": "C", "TZ": "UTC", "PYTHONHASHSEED": "1",
                "PATH": str(args.rustc.parent) + os.pathsep + env["PATH"]})
    repo = Path(invoke(["git", "rev-parse", "--show-toplevel"], Path.cwd(), env).decode().strip())
    clang = ["--clang", args.clang]
    if args.clang_libdir:
        clang += ["--clang-libdir", args.clang_libdir]
    crosses = [*clang, "--lld", args.lld, "--qemu-aarch64", args.qemu_aarch64, "--qemu-riscv64", args.qemu_riscv64]
    with tempfile.TemporaryDirectory(prefix="rt00-ffi-archive-") as directory:
        root = Path(directory)
        capture(repo, root, env)
        go = ["--go", args.go, "--go-cache", args.go_cache or root / "go-cache"]
        suites = {
            "loader": ("FFI-LOADER-SCOPE-01", "observations.json", ["--out"]),
            "header": ("FFI-HEADER-IMPORT-01", "observations.json",
                       [*clang, "--sqlite-include", args.sqlite_include,
                        "--sqlite-library", args.sqlite_library, "--crypto-library", args.crypto_library,
                        "--libc-library", args.libc_library, "--out"]),
            "callback": ("FFI-CALLBACK-LIFETIME-01", "observations.json", ["--rustc", args.rustc, "--out"]),
            "managed": ("FFI-MANAGED-CALLBACK-01", "observations.json", [*go, "--out"]),
            "aggregate": ("FFI-AGGREGATE-CROSS-ABI-01", "observations.json", [*crosses, "--out"]),
            "variadic": ("FFI-VARIADIC-ABI-01", "observations.json", [*crosses, "--out"]),
            "package": ("FFI-CROSS-BUILD-CACHE-01", "observations.json", [*crosses, "--out"]),
            "conditional": ("FFI-CONDITIONAL-RECEIPTS-01", "evidence.json",
                            [*go, "--lean", args.lean, "--output"]),
        }
        ledgers, inventory = {}, {}
        for name, (folder, manifest, options) in suites.items():
            ledgers[name], inventory[name] = replay(repo, root, folder, manifest, options, env)
        result = {"baseline": BASE, "byte_matched_replays": inventory,
                  "checked_claims": comparison(ledgers)}
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
