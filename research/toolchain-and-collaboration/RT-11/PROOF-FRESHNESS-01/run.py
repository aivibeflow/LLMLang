#!/usr/bin/env python3
"""Compare scoped proof reuse and archived Lean artifact compatibility."""

import argparse
from hashlib import file_digest, sha256
import json
import os
from pathlib import Path
import platform
import re
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
REVISIONS = {
    "4.34.0": "293d5d0c0c3f3dded4688b3ccd6a33939ac5102b",
    "4.36.0": "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9",
}
SOURCES = {
    "baseline": "grow x = x + 1\n",
    "formatting": "grow x =  x  +  1  \n",
    "refactor": "grow x = 1 + x\n",
    "changed": "grow x = x + 2\n",
    "refuted": "grow x = x\n",
}
PROOF_TERMS = {
    "x + 1": "Nat.lt_succ_self x",
    "1 + x": "Eq.mp (congrArg (fun k => x < k) (Nat.add_comm x 1)) (Nat.lt_succ_self x)",
    "x + 2": "Nat.lt_trans (Nat.lt_succ_self x) (Nat.lt_succ_self (x + 1))",
    "x": "Nat.lt_succ_self x",
}
CHECKER_FLAGS = ("-DwarningAsError=true",)
PROOF = "\n\ntheorem increases (x : Nat) : x < grow x :=\n  {term}\n\n#print axioms increases\n"


def hash_bytes(data):
    return sha256(data).hexdigest()


def digest_file(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def key(domain, *values):
    return hash_bytes(json.dumps((domain, values), separators=(",", ":")).encode("ascii"))


def invoke(lean, root, *args, search=None):
    environment = dict(os.environ)
    environment.pop("LEAN_PATH", None)
    if search is not None:
        environment["LEAN_PATH"] = str(search)
    return subprocess.run([lean, *args], cwd=root, env=environment, capture_output=True, timeout=30)


def proof_source(body):
    return (f"def grow (x : Nat) : Nat := {body}" + PROOF.format(term=PROOF_TERMS[body])).encode("ascii")


def library_profile(lean, root):
    result = invoke(lean, root, "--print-prefix")
    if result.returncode or result.stderr:
        raise ValueError((result.stdout + result.stderr).decode())
    library = Path(result.stdout.decode().strip()) / "lib" / "lean"
    files = sorted([*library.glob("Init.olean*"), *(library / "Init").rglob("*.olean*")])
    if not files:
        raise ValueError("Could not resolve the explicit Lean Init library profile")
    records = [(path.relative_to(library).as_posix(), digest_file(path)) for path in files]
    libraries = sorted([*library.glob("libleanshared*.so"), library / "libInit_shared.so"])
    return {
        "init_objects": len(records), "init_manifest_sha256": key("lean-init/1", records),
        "shared_libraries_sha256": {path.name: digest_file(path) for path in libraries},
    }


def run_check(lean, root, body, report, successful):
    proof_bytes = proof_source(body)
    path = root / "Saved.lean"
    path.write_bytes(proof_bytes)
    result = invoke(lean, root, *CHECKER_FLAGS, path.name)
    output = result.stdout + result.stderr
    if successful:
        if result.returncode or result.stderr or b"'increases'" not in result.stdout:
            raise ValueError(output.decode())
    elif result.returncode == 0 or b"Type mismatch" not in output:
        raise ValueError(output.decode())
    return {
        "source_sha256": hash_bytes(SOURCES[report].encode("utf-8")),
        "subject": key("typed-body/1", body),
        "proof_input_sha256": hash_bytes(proof_bytes),
        "outcome": "proved" if successful else "refused",
        "exit_code": result.returncode,
        "output": output.decode(),
    }


def binary_compatibility(tools, root):
    artifacts = {}
    for version, tool in tools.items():
        directory = root / version
        directory.mkdir()
        (directory / "Saved.lean").write_bytes(proof_source("x + 1"))
        result = invoke(tool, directory, *CHECKER_FLAGS, "-o", "Saved.olean", "Saved.lean")
        if result.returncode or result.stderr:
            raise ValueError((result.stdout + result.stderr).decode())
        artifacts[version] = directory / "Saved.olean"
    importer = root / "Read.lean"
    importer.write_text("import Saved\n#print axioms increases\n", encoding="utf-8")
    cases = {}
    for builder, path in artifacts.items():
        for reader, tool in tools.items():
            result = invoke(tool, root, *CHECKER_FLAGS, importer.name, search=path.parent)
            output = (result.stdout + result.stderr).decode()
            admitted = result.returncode == 0
            if admitted != (builder == reader):
                raise ValueError(f"Unexpected import result for {builder} -> {reader}: {output}")
            if not admitted and not any(word in output.lower() for word in ("header", "format", "version")):
                raise ValueError(f"Unexpected import failure: {output}")
            cases[f"{builder}->{reader}"] = {
                "builder": builder, "reader": reader, "admitted": admitted,
                "exit_code": result.returncode,
                "diagnostic": output.replace(str(root), "<fixture>"),
            }
    return {v: hash_bytes(p.read_bytes()) for v, p in artifacts.items()}, cases


def compare(tools):
    host = {"system": platform.system(), "architecture": platform.machine(),
            "kernel": platform.release(), "libc": platform.libc_ver()}
    with TemporaryDirectory(prefix="llmlang-proof-freshness-") as directory:
        root = Path(directory)
        runs, semantic_controls, checker_versions = {}, {}, {}
        for version, tool in tools.items():
            version_output = invoke(tool, root, "--version")
            description = version_output.stdout.decode().strip()
            if version_output.returncode or REVISIONS[version] not in description:
                raise ValueError(f"Expected pinned Lean {version}: {description}")
            checker = {
                "version": description, "executable_sha256": digest_file(tool),
                "library_profile": library_profile(tool, root), "flags": CHECKER_FLAGS,
            }
            checker_versions[version] = checker
            controls = invoke(tool, HERE, *CHECKER_FLAGS, "SemanticControls.lean")
            if controls.returncode or controls.stderr:
                raise ValueError((controls.stdout + controls.stderr).decode())
            semantic_controls[version] = controls.stdout.decode()
            for label, source in SOURCES.items():
                body = " ".join(re.fullmatch(r"grow x =\s*(x(?:\s*\+\s*[12])?|1\s*\+\s*x)\s*", source)[1]
                                .replace("+", " + ").split())
                outcome = run_check(tool, root, body, label, label != "refuted")
                outcome["execution_key"] = key("lean-execution/1", outcome["proof_input_sha256"], checker, host)
                outcome["source_receipt"] = key("source-evidence/1", outcome["execution_key"],
                                               outcome["source_sha256"])
                runs[f"{label}/{version}"] = outcome
        hashes, compiled = binary_compatibility(tools, root)
    anchor = runs["baseline/4.34.0"]
    scope = {}
    for label, value in runs.items():
        scope[label] = {field: value[field] == anchor[field]
                        for field in ("subject", "execution_key", "source_receipt")}
    return {
        "schema": "llmlang-impact-and-proof-freshness/1", "python": platform.python_version(), "host": host,
        "sources": SOURCES,
        "sources_sha256": {name: hash_bytes((HERE / name).read_bytes())
                           for name in ("run.py", "SemanticControls.lean")},
        "checkers": checker_versions, "checked_source_runs": runs, "semantic_controls": semantic_controls,
        "compiled_artifacts_sha256": hashes, "compiled_imports": compiled,
        "comparison_to_baseline_434": scope,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean-434", required=True, type=Path)
    parser.add_argument("--lean-436", required=True, type=Path)
    cli = parser.parse_args()
    print(json.dumps(compare({"4.34.0": cli.lean_434.resolve(), "4.36.0": cli.lean_436.resolve()}), indent=2))
