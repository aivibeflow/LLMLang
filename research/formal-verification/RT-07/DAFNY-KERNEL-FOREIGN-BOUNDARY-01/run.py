"""Measure a checked Dafny lookup and its trusted C ABI boundary."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib import import_module
from itertools import product
import json
import os
from pathlib import Path
import platform
import random
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
LIMIT = 1 << 64
MAX_WORD = LIMIT - 1
ENTRY_BYTES = 16
SEED = 20261125
ARCHIVE_SHA256 = "a46a9ff7cdd720f7955854c78e95df13f4cfe6b80691b05f8654fe19e8267179"
NATIVE_ROUTES = {
    "c_checked": ("resolve_checked", False),
    "c_wrapping": ("resolve_wrapping", False),
    "c_overflow_first": ("resolve_overflow_first", False),
    "abi_signed_result": ("resolve_checked", True),
}
THRESHOLD = """    var maximum := (Limit - 1 - (base as int)) / EntryBytes;
    if slot as int > maximum {
      return 2, 0;
    }
    var selected := base as int + EntryBytes * (slot as int);
"""
WRAPPING = """    var selected := (base as int + EntryBytes * (slot as int)) % Limit;
"""


def command(directory, *args, check=True):
    return subprocess.run([str(argument) for argument in args], cwd=directory,
                          capture_output=True, text=True, check=check, timeout=60,
                          env={**os.environ, "LC_ALL": "C"})


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def oracle(base, count, slot):
    if slot >= count:
        return (1, 0)
    selected = base + ENTRY_BYTES * slot
    if selected >= LIMIT:
        return (2, 0)
    return (0, selected)


def corpus():
    bases = (0, 1, 15, 16, (1 << 63) - 1, 1 << 63, (1 << 63) + 15,
             LIMIT - 33, LIMIT - 32, LIMIT - 17, LIMIT - 16, MAX_WORD)
    bounds = (0, 1, 2, 3, 15, 16, (1 << 60) - 1, 1 << 60, (1 << 60) + 1, 1 << 63, MAX_WORD)
    cases = set(product(bases, bounds, bounds))
    directed = len(cases)
    rng = random.Random(SEED)
    for _ in range(64):
        base = rng.getrandbits(64)
        overflow_at = (MAX_WORD - base) // ENTRY_BYTES + 1
        for delta in (-1, 0, 1):
            slot = overflow_at + delta
            cases.add((base, slot + 1, slot))
            cases.add((base, slot, slot))
    return sorted(cases), directed


def proof_result(run):
    text = run.stdout + run.stderr
    match = re.search(r"Dafny program verifier finished with (\d+) verified, (\d+) errors?", text)
    if match is None:
        raise ValueError((run.returncode, text))
    verified, errors = map(int, match.groups())
    return {"verified": verified, "errors": errors, "exit": run.returncode,
            "foreign_assumption_warning": "can not guarantee that its implementation satisfies its post-conditions" in text,
            "postcondition_failure_reported": "a postcondition could not be proved" in text}


def build(directory, dafny, solvers):
    source = HERE / "Lookup.dfy"
    shutil.copyfile(source, directory / source.name)
    shutil.copyfile(HERE / "ffi_bridge.py", directory / "ffi_bridge.py")
    data = source.read_text(encoding="utf-8")
    assert data.count(THRESHOLD) == 1
    (directory / "DroppedGuard.dfy").write_text(data.replace(THRESHOLD, WRAPPING), encoding="utf-8")
    common = ("--cores", "1", "--verification-time-limit", "15")
    profiles = {
        "default_warning_gate": ((), "Lookup.dfy"),
        "warnings_visible": (("--allow-warnings",), "Lookup.dfy"),
        "explicit_external_contracts": (("--allow-external-contracts",), "Lookup.dfy"),
        "local_dropped_guard": (("--allow-external-contracts",), "DroppedGuard.dfy"),
    }
    observations = {}
    for version, solver in solvers.items():
        results = {}
        for name, (flags, path) in profiles.items():
            run = command(directory, dafny, "verify", *common, "--solver-path", solver, *flags, path,
                          check=False)
            results[name] = proof_result(run)
        default = results["default_warning_gate"]
        assert default == {"verified": 5, "errors": 0, "exit": 2, "foreign_assumption_warning": True,
                           "postcondition_failure_reported": False}
        assert results["warnings_visible"] == default | {"exit": 0}
        assert results["explicit_external_contracts"] == default | {"exit": 0, "foreign_assumption_warning": False}
        mutant = results["local_dropped_guard"]
        assert (mutant["errors"], mutant["postcondition_failure_reported"]) == (1, True), mutant
        observations[version] = results
    assert observations["4.12.1"] == observations["4.14.1"]
    build_run = command(directory, dafny, "build", "--target", "py", *common,
                        "--solver-path", solvers["4.12.1"], "--allow-warnings", "Lookup.dfy", "ffi_bridge.py")
    assert proof_result(build_run) == observations["4.12.1"]["warnings_visible"]
    generated = directory / "Lookup-py"
    files = sorted(generated.rglob("*.py"))
    assert (generated / "ffi_bridge.py").read_bytes() == (HERE / "ffi_bridge.py").read_bytes()
    assert "ffi_bridge.default__.resolve(base, count, slot)" in (generated / "Client.py").read_text()
    return generated, observations, sha(directory / "DroppedGuard.dfy"), {
        str(path.relative_to(generated)): sha(path) for path in files
    }


def compare_native(directory, generated, inputs, gcc):
    sys.path.insert(0, str(generated))
    core = import_module("Core").default__
    client = import_module("Client").default__
    bridge = import_module("ffi_bridge")
    expected = [oracle(*words) for words in inputs]
    assert [core.Expected(*words) for words in inputs] == expected
    assert [core.Checked(*words) for words in inputs] == expected
    libraries = {}
    all_outputs = {}
    for level in (0, 2):
        name = f"O{level}"
        library = directory / f"provider-{name}.so"
        command(directory, gcc, "-std=c11", "-Wall", "-Wextra", "-Werror", f"-{name}",
                "-shared", "-fPIC", "provider.c", "-o", library.name)
        libraries[name] = sha(library)
        outputs = {}
        for route, (symbol, signed) in NATIVE_ROUTES.items():
            bridge.configure(library, symbol, signed_result=signed)
            outputs[route] = [client.ViaForeign(*words) for words in inputs]
        all_outputs[name] = outputs
    assert all_outputs["O0"] == all_outputs["O2"]
    outputs = all_outputs["O0"]
    assert outputs["c_checked"] == expected
    wrong = {}
    observations = []
    for route, values in outputs.items():
        wrong[route] = sum(result != correct for result, correct in zip(values, expected, strict=True))
        if route != "c_checked":
            assert wrong[route] > 0
    for index, (words, correct) in enumerate(zip(inputs, expected, strict=True)):
        observations.append({"input": list(map(str, words)), "expected": [correct[0], str(correct[1])],
                             "native": {route: [results[index][0], str(results[index][1])]
                                        for route, results in outputs.items()}})
    return wrong, observations, dict(Counter(status for status, _ in expected)), libraries


def run(directory, args):
    assert platform.system() == "Linux" and platform.machine() == "x86_64"
    dafny = args.dafny.resolve()
    gcc = args.gcc
    solvers = {version: dafny.parent / "z3" / "bin" / f"z3-{version}" for version in ("4.12.1", "4.14.1")}
    assert sha(args.release) == ARCHIVE_SHA256
    shutil.copyfile(HERE / "provider.c", directory / "provider.c")
    generated, proofs, mutated_digest, generated_digests = build(directory, dafny, solvers)
    inputs, directed = corpus()
    wrong, observations, statuses, libraries = compare_native(directory, generated, inputs, gcc)
    assert any(row["input"] == [str(LIMIT - 16), "2", "1"] and row["expected"] == [2, "0"]
               for row in observations)
    tools = {"dafny": command(directory, dafny, "--version").stdout.strip(),
             "z3": {version: command(directory, solver, "--version").stdout.strip()
                    for version, solver in solvers.items()},
             "gcc": command(directory, gcc, "--version").stdout.splitlines()[0],
             "python": platform.python_version()}
    return {"schema": "llmlang-dafny-kernel-ffi-lookup/1", "tools": tools,
            "dafny_release_sha256": ARCHIVE_SHA256, "z3_sha256": {version: sha(solver) for version, solver in solvers.items()},
            "sources": {name: sha(HERE / name) for name in ("Lookup.dfy", "run.py", "provider.c", "ffi_bridge.py")},
            "local_dropped_guard_sha256": mutated_digest, "generated_python_sha256": generated_digests,
            "provider_shared_object_sha256": libraries, "proofs": proofs,
            "seed": SEED, "inputs": len(inputs), "directed_inputs": directed,
            "expected_status_counts": statuses, "native_mismatches_per_profile": wrong,
            "observations": observations}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dafny", type=Path, required=True)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--gcc", default="gcc")
    with TemporaryDirectory(prefix="llmlang-dafny-kernel-lookup-") as scratch:
        evidence = run(Path(scratch), parser.parse_args())
    measurements = evidence.pop("observations")
    print(json.dumps(evidence, indent=2).removesuffix("\n}") + ',\n  "observations": [')
    print(",\n".join("    " + json.dumps(row, separators=(",", ":")) for row in measurements))
    print("  ]\n}")
