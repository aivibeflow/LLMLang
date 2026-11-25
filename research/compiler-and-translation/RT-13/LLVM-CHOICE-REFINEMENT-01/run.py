#!/usr/bin/env python3
"""Separate structural checks, scoped validator verdicts and choice sets."""

from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
REVISION = "5cb0641ad4f250ecb8fcf8d1c62335d52cc016c3"
ARCHIVE = "research/compiler-and-translation/RT-13"
VALIDATORS = f"{ARCHIVE}/LLVM-VALIDATORS-01"
F64 = f"{ARCHIVE}/LLVM-F64-I64-LOWERING-01"


def archived(path, expected):
    data = subprocess.check_output(["git", "show", f"{REVISION}:{path}"])
    if sha256(data).hexdigest() != expected:
        raise AssertionError(f"Source digest mismatch: {path}")
    return data


def verify_module(path, assembler, opt):
    bitcode = path.with_suffix(".bc")
    subprocess.run([assembler, str(path), "-o", str(bitcode)], check=True)
    subprocess.run([opt, "-passes=verify", "-disable-output", str(bitcode)], check=True)


def reconcile(directory, assembler, opt):
    original = json.loads(archived(f"{VALIDATORS}/evidence.json",
                                  "ee2737a92fae6a147fa69b0d4b1d9d70f680302e356251273fc2345bdf72627b"))
    stock = json.loads(archived(f"{VALIDATORS}/stock-eh-evidence.json",
                               "2954d01491709a61486ccde8bdf9e5b8c2b0c673930a4990a018cf2f9827048a"))
    assert original["inputs_sha256"] == stock["inputs_sha256"]
    assert original["cases"] == stock["cases"]
    assert original["changed_vellvm_assertion"] == stock["changed_vellvm_assertion"]
    assert original["changed_vellvm_assertion"]["failed"] == 1
    modules = {}
    for case, result in original["cases"].items():
        name = f"{case}.ll"
        path = directory / name
        exact = original["inputs_sha256"][name]
        path.write_bytes(archived(f"{VALIDATORS}/{name}", exact))
        verify_module(path, assembler, opt)
        modules[case] = {"sha256": exact, "structural_verifier": "accepted",
                         "archived_alive2": result["alive2"],
                         "archived_vellvm_assertions": result["vellvm"]}

    conversion = json.loads(archived(f"{F64}/evidence.json",
                                    "d451dad410054a0d6a658f651a27a42ff61db392ca6e06ccdb2b8be1c80b405e"))
    exact = conversion["source_sha256"]["lowerings.ll"]
    path = directory / "lowerings.ll"
    path.write_bytes(archived(f"{F64}/lowerings.ll", exact))
    verify_module(path, assembler, opt)
    conversions = {}
    for label, verdict in conversion["original_refinement"].items():
        conversions[label] = {
            "archived_alive2": verdict,
            "archived_vellvm_assertions": conversion["vellvm"][label]["per_extraction"],
            "archived_native_mismatch_count": conversion["native_mismatches"].get(label),
        }
    return {
        "shared_five_modules": modules,
        "f64_module": {"sha256": exact, "structural_verifier": "accepted", "cases": conversions},
    }


def allowed(bit, unknown):
    bits = range(2) if unknown else (bit,)
    pin = 0 if unknown else bit
    return {
        "stable": {left * 2 + (1 - left) for left in bits},
        "independent": {left * 2 + (1 - right) for left, right in product(bits, repeat=2)},
        "pin": {pin * 2 + (1 - pin)},
    }


def classification(choices):
    rows = {}
    for source, target in product(choices, repeat=2):
        extra = choices[target] - choices[source]
        rows[f"{source}_to_{target}"] = {"refines": not extra, "extra_target_values": sorted(extra)}
    return rows


def choice_experiment(directory, assembler, opt, clang):
    path = directory / "freeze.ll"
    path.write_bytes((HERE / path.name).read_bytes())
    verify_module(path, assembler, opt)
    possible = {(bit, unknown): allowed(bit, unknown) for bit, unknown in product(range(2), repeat=2)}
    records = {}
    for level in ("O0", "O3"):
        out = directory / f"choice-{level}"
        subprocess.run([clang, f"-{level}", "-Wno-override-module", str(path),
                        str(HERE / "harness.c"), "-o", str(out)], check=True)
        proc = subprocess.run([str(out)], check=True, text=True, capture_output=True)
        rows = [tuple(map(int, row.split())) for row in proc.stdout.splitlines()]
        if proc.stderr or [(row[0], row[1]) for row in rows] != list(possible):
            raise AssertionError(f"Unexpected native output under {level}")
        for bit, unknown, *observed in rows:
            for result, outcomes in zip(observed, possible[bit, unknown].values(), strict=True):
                if result not in outcomes:
                    raise AssertionError((level, (bit, unknown), result, outcomes))
        # Native results when LLVM can choose an arbitrary value need not be stable across hosts.
        # Record admitted memberships and the exact supplied LLVM program instead of those values.
        records[level] = {"admitted_memberships": sum(len(row) - 2 for row in rows),
                          "tests": len(rows)}
    return {
        "builds": records,
        "modeled_outcomes": {f"{bit},{unknown}": {name: sorted(values) for name, values in row.items()}
                             for (bit, unknown), row in possible.items()},
        "choice_case_translation_directions": classification(possible[0, 1]),
    }


def main():
    assembler = os.environ.get("LLVM_AS", "llvm-as")
    opt = os.environ.get("OPT", "opt")
    clang = os.environ.get("CLANG", "clang")
    versions = {label: subprocess.check_output([tool, "--version"], text=True).splitlines()[0]
                for label, tool in (("asm", assembler), ("opt", opt), ("clang", clang))}
    with tempfile.TemporaryDirectory() as build:
        directory = Path(build)
        history = reconcile(directory, assembler, opt)
        choices = choice_experiment(directory, assembler, opt, clang)
    print(json.dumps({
        "schema": "llmlang-llvm-validator-and-choice-scope/1", "python": platform.python_version(),
        "archive_revision": REVISION, "tools": versions,
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "Choice.lean", "freeze.ll", "harness.c", "axioms.txt")},
        "archives": history, "fresh_choice_experiment": choices,
    }, indent=2))


if __name__ == "__main__":
    main()
