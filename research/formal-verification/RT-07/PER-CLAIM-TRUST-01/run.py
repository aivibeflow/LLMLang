#!/usr/bin/env python3
"""Compile and reopen exactly typed Lean claims to compare their trust dependencies."""

from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
MODULES = ("Boundary", "Routes", "Wrapped", "Audit", "WrongExpected", "Placeholder")
CLOSED = ("wrappedKernel", "wrappedForeign", "wrappedNative", "premiseDischarged")
AXIOMS = re.compile(r"^'([^']+)' (?:does not depend on any axioms|depends on axioms: \[([^]]+)\])$")
FOREIGN = "TrustBoundary.inputIsNine"
NATIVE = "TrustBoundary.nativeReflection._native.native_decide.ax_1_1"


def execute(args, root):
    environment = {**os.environ, "LEAN_PATH": ".", "LC_ALL": "C"}
    return subprocess.run(args, cwd=root, env=environment, capture_output=True,
                          text=True, check=False, timeout=45)


def output(result, expected=0):
    if result.returncode != expected or result.stderr:
        raise AssertionError((result.args, result.returncode, result.stdout, result.stderr))
    return result.stdout


def assumptions(transcript):
    found = {}
    for line in transcript.splitlines():
        match = AXIOMS.fullmatch(line)
        if match:
            name, dependencies = match.groups()
            if name in found:
                raise AssertionError(f"Repeated axiom row for {name}")
            found[name] = dependencies.split(", ") if dependencies else []
    return found


def adjudicate(name, dependencies, trusted):
    if "sorryAx" in dependencies:
        return "forbidden-placeholder"
    if name == "openPremise":
        return "conditional-explicit-premise"
    if not set(dependencies) <= trusted:
        return "unadmitted-axioms"
    if FOREIGN in dependencies:
        return "conditional-imported-premise"
    if NATIVE in dependencies:
        return "closed-with-native-trust"
    return "closed-kernel-only"


def run():
    lean = shutil.which("lean")
    if lean is None:
        raise RuntimeError("The pinned Lean executable must be on PATH")
    with TemporaryDirectory(prefix="llmlang-claim-trust-") as temporary:
        root = Path(temporary)
        for module in MODULES:
            shutil.copyfile(HERE / f"{module}.lean", root / f"{module}.lean")
        for module in MODULES[:3]:
            output(execute([lean, "-DwarningAsError=true", "-o", f"{module}.olean", f"{module}.lean"], root))
        normal = output(execute([lean, "-DwarningAsError=true", "Audit.lean"], root))
        rechecked = output(execute([lean, "-t", "0", "-DwarningAsError=true", "Audit.lean"], root))
        if normal != rechecked:
            raise AssertionError("Rechecking the imports changed the observed declarations")
        wrong = output(execute([lean, "-t", "0", "-DwarningAsError=true", "WrongExpected.lean"], root), 1)
        if "Type mismatch" not in wrong or "openPremise" not in wrong:
            raise AssertionError(wrong)
        permissive = output(execute([lean, "-DwarningAsError=false", "Placeholder.lean"], root))
        strict = output(execute([lean, "-DwarningAsError=true", "Placeholder.lean"], root), 1)
        if "warning: declaration uses" not in permissive or "error: declaration uses" not in strict:
            raise AssertionError((permissive, strict))
        detected = assumptions(normal + permissive)
        expected = {
            "wrappedKernel": [], "wrappedForeign": [FOREIGN], "wrappedNative": [NATIVE],
            "openPremise": [], "premiseDischarged": [],
            "unrelatedAgreement": ["TrustBoundary.unrelatedAgreement"], "placeholder": ["sorryAx"],
        }
        actual = {name.removeprefix("TrustBoundary."): axioms for name, axioms in detected.items()}
        if actual != expected or assumptions(strict) != assumptions(permissive):
            raise AssertionError((actual, expected, strict))
        compiled_hashes = {f"{module}.olean": sha256((root / f"{module}.olean").read_bytes()).hexdigest()
                           for module in MODULES[:3]}
        version = output(execute([lean, "--version"], root)).strip()
        binary_sha256 = sha256(Path(lean).resolve().read_bytes()).hexdigest()

    policies = {
        "kernel_only": set(), "reviewed_imported_premise": {FOREIGN},
        "native_evaluation_allowed": {NATIVE},
    }
    declarations = {}
    for name, axioms in actual.items():
        if name == "unrelatedAgreement":
            continue
        declarations[name] = {
            "statement": "open-premise" if name == "openPremise" else "closed",
            "axioms": axioms,
            "decisions": {key: adjudicate(name, axioms, allow) for key, allow in policies.items()},
        }
    return {
        "schema": "llmlang-per-claim-trust/1", "python": platform.python_version(),
        "lean": version, "lean_executable_sha256": binary_sha256,
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", *(f"{module}.lean" for module in MODULES))},
        "compiled_module_sha256": compiled_hashes,
        "imports_rechecked_equal": True,
        "expected_closed_type_checked": CLOSED,
        "conditional_as_closed_exit": 1,
        "placeholder_exit_permissive": 0,
        "placeholder_exit_warnings_are_errors": 1,
        "unused_imported_axiom": actual["unrelatedAgreement"][0],
        "declarations": declarations,
        "transcripts": {"import": rechecked.splitlines(), "wrong_type": wrong.splitlines(),
                        "placeholder": permissive.splitlines(), "strict_placeholder": strict.splitlines()},
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
