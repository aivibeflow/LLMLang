#!/usr/bin/env python3
"""Compare exact conformance scope on native and WebAssembly provider artifacts."""

import argparse
import ctypes
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import shutil
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
VALUES = tuple(range(-2, 6))
CONTRACT = "clamp-to-zero-through-three-with-declared-event/1"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(raw):
    return sha256(raw).hexdigest()


def execute(args, root, raw=None):
    return subprocess.run(args, cwd=root, input=raw, capture_output=True, check=True, timeout=45).stdout


def tool(command, root):
    path = Path(shutil.which(command))
    version = execute([path, "--version"], root).decode().splitlines()[0]
    return {"version": version, "executable_sha256": digest(path.read_bytes())}


def expected(active):
    return [(value, int(active), 2 * min(3, max(0, value)) + int(active and not 0 <= value <= 3))
            for value in VALUES]


def native(artifact, requests):
    api = ctypes.CDLL(artifact)
    evaluate = api.bounded_value
    evaluate.argtypes = (ctypes.c_int, ctypes.c_int)
    evaluate.restype = ctypes.c_int
    return [evaluate(value, active) for value, active in requests]


def wasm(artifact, requests, root):
    return json.loads(execute(["node", HERE / "wasm.mjs", artifact], root, canonical(requests)))


def build(root, compiler, linker, flags, mode, wasm_target):
    extra = ["-DOMIT_EVENT"] if mode == "drop_event" else []
    common = [flags, "-std=c17", "-Wall", "-Wextra", "-Werror", *extra]
    if wasm_target:
        name = "provider.wasm"
        compile_ = ["--target=wasm32-unknown-unknown", "-ffreestanding",
                    *common, "-c", "provider.c", "-o", "provider.o"]
        link = ["--no-entry", "--export=bounded_value", "provider.o", "-o", name]
        execute([compiler, *compile_], root)
        execute([linker, *link], root)
        recipe = {"compiler_argv": compile_, "linker_argv": link}
    else:
        name = "provider.so"
        driver = ["-fPIC", "-shared", "-Wl,--build-id=none", *common, "provider.c", "-o", name]
        execute([compiler, *driver], root)
        recipe = {"compiler_driver_argv": driver}
    return root / name, recipe


def admit(request, receipt, admitted):
    fingerprint = digest(canonical(request))
    return (receipt["subject"] == request and receipt["key"] == fingerprint
            and admitted.get(fingerprint) == receipt["observations_sha256"])


def compare(args):
    if platform.system() != "Linux" or platform.machine() != "x86_64" or ctypes.sizeof(ctypes.c_int) != 4:
        raise RuntimeError("The native fixture requires x86-64 Linux with 32-bit C int")
    requests = list(product(VALUES, (0, 1)))
    body = (HERE / "provider.c").read_bytes()
    contract = {"id": CONTRACT, "reference_sha256": digest(canonical(expected(False) + expected(True)))}
    checker = {name: digest((HERE / name).read_bytes()) for name in ("run.py", "wasm.mjs")}
    samples = []
    cases = (
        ("gcc_native_O0", "gcc", "-O0", False),
        ("clang_native_O2", args.clang, "-O2", False),
        ("clang_wasm_O0", args.clang, "-O0", True),
        ("clang_wasm_O2", args.clang, "-O2", True),
    )
    with TemporaryDirectory(prefix="llmlang-target-receipt-") as temp:
        root = Path(temp)
        tool_data = {"gcc": tool("gcc", root), "clang": tool(args.clang, root),
                     "ld": tool("ld", root), "wasm_ld": tool(args.wasm_ld, root), "node": tool("node", root)}
        for (name, compiler, flag, is_wasm), mode in product(cases, ("exact", "drop_event")):
            work = root / f"{name}-{mode}"
            work.mkdir()
            (work / "provider.c").write_bytes(body)
            artifact, recipe = build(work, compiler, args.wasm_ld, flag, mode, is_wasm)
            digest_, artifact_bytes = digest(artifact.read_bytes()), artifact.stat().st_size
            rows = wasm(artifact, requests, work) if is_wasm else native(artifact, requests)
            profile = "wasm32-export-i32" if is_wasm else "x86_64-sysv-c-int"
            for active in (False, True):
                actual = [(x, flag_, output) for (x, flag_), output in zip(requests, rows) if flag_ == active]
                reference = expected(active)
                disagreements = [received for received, proposed in zip(actual, reference) if received != proposed]
                if len(actual) != len(reference) or len(rows) != len(requests):
                    raise AssertionError("Incomplete native observation table")
                want = 4 if mode == "drop_event" and active else 0
                if len(disagreements) != want:
                    raise AssertionError((name, mode, active, disagreements))
                subject = {
                    "semantic_input": {"operation": "bounded-value/1", "source": digest(body),
                                       "provider": mode, "input_values": VALUES},
                    "contract": contract, "assumption": {"callback_observable": active},
                    "checker": checker,
                    "target": profile, "artifact_sha256": digest_,
                    "compiler": tool_data["gcc" if compiler == "gcc" else "clang"],
                    "linker": tool_data["wasm_ld" if is_wasm else "ld"],
                    "executor": tool_data["node"] if is_wasm else {"python": platform.python_version(),
                        "api": "ctypes.CDLL", "c_int_bytes": ctypes.sizeof(ctypes.c_int)},
                    "recipe": recipe,
                }
                samples.append({
                    "profile": name, "provider": mode, "artifact_bytes": artifact_bytes,
                    "key": digest(canonical(subject)), "subject": subject, "validated": not disagreements,
                    "observations_sha256": digest(canonical(actual)), "refutations": disagreements,
                })

    verified = [sample for sample in samples if sample["validated"]]
    registry = {sample["key"]: sample["observations_sha256"] for sample in verified}
    if len(registry) != len(verified):
        raise AssertionError("Different checked subjects collapsed")
    ordered_reuse = [(old, current) for old, current in product(verified, samples)]
    actual_allowed = sum(admit(current["subject"], old, registry) for old, current in ordered_reuse)
    same_observations_other_subject = sum(
        old["observations_sha256"] == current["observations_sha256"] and old["key"] != current["key"]
        for old, current in ordered_reuse
    )
    if actual_allowed != len(verified):
        raise AssertionError("Fresh receipt did not exactly match one requested subject")
    base = verified[0]
    subject = base["subject"]
    replacements = {
        "semantic_input": {**subject["semantic_input"], "operation": "bounded-value/2"},
        "contract": {**subject["contract"], "id": "clamp-observed-value-only/1"},
        "checker": {**subject["checker"], "run.py": "0" * 64},
        "assumption": {"callback_observable": True},
        "target": "wasm32-export-i32",
        "artifact_sha256": "0" * 64,
        "compiler": tool_data["clang"],
        "linker": tool_data["wasm_ld"],
        "executor": {**subject["executor"], "api": "direct-native-execution"},
        "recipe": {"compiler_driver_argv": [
            "-O2" if arg == "-O0" else arg for arg in subject["recipe"]["compiler_driver_argv"]
        ]},
    }
    checks = {field: admit({**subject, field: replacement}, base, registry)
              for field, replacement in replacements.items()}
    if any(checks.values()):
        raise AssertionError("A single-field edit reused old evidence")
    return {
        "schema": "llmlang-cross-target-conformance/1", "python": platform.python_version(),
        "inputs_sha256": {name: digest((HERE / name).read_bytes()) for name in ("run.py", "provider.c", "wasm.mjs")},
        "tools": tool_data, "scopes": len(samples), "observations": len(VALUES) * len(samples),
        "checked_scopes": len(verified), "refuted_scopes": len(samples) - len(verified),
        "ordered_receipt_reuse_pairs": len(ordered_reuse), "exact_reuse_admissions": actual_allowed,
        "same_observations_different_scope": same_observations_other_subject,
        "single_field_reuse_controls": checks, "samples": samples,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", type=Path, required=True)
    parser.add_argument("--wasm-ld", type=Path, required=True)
    print(json.dumps(compare(parser.parse_args()), indent=2))
