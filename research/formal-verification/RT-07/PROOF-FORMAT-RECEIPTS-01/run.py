#!/usr/bin/env python3
"""Compare explicit Lean and CPC proof receipt formats on the same typed claims."""

import argparse
from io import BytesIO
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from tarfile import open as tar_open
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
SOURCE_GATE = HERE.parent / "SOURCE-PROOF-REBINDING-01"
sys.path.insert(0, str(SOURCE_GATE))
from run import BASELINE, LOGOS_REV, PROTOTYPE, ROOT, digest, execute, rebuild

VALUES = {7: "seven", 8: "eight"}
LEAN_FORMAT = "lean-source/1"
CPC_FORMAT = "cpc-text/1"
SCHEMA = "llmlang-proof-receipt/1"


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")


def term_to_lean(term, declarations):
    op = term["op"]
    args = [term_to_lean(child, declarations) for child in term["args"]]
    atom = term["atom"]
    if op == "symbol" and not args and atom in declarations:
        return atom
    if op == "int" and not args and type(atom) is int:
        return f"({atom} : Int)"
    if op == "bool" and not args and type(atom) is bool:
        return "True" if atom else "False"
    if op == "not" and len(args) == 1:
        return f"(¬ {args[0]})"
    if op in ("eq", "or") and len(args) == 2:
        connective = {"eq": "=", "or": "∨"}[op]
        return f"({args[0]} {connective} {args[1]})"
    if op == "ite" and len(args) == 3:
        return f"(if {args[0]} then {args[1]} else {args[2]})"
    raise ValueError("The fixture has no interpretation for this term")


def kernel_check(wire, selected_theorem, root, env):
    query = json.loads(wire)
    declarations = [item["name"] for item in query["declarations"]]
    if len(declarations) != 2 or any(
        item["sort"] != "Int" or not re.fullmatch(r"i_[0-9]+_[LR]", item["name"])
        for item in query["declarations"]
    ):
        raise ValueError("The proof fixture admits two declared Int symbols")
    left, right = declarations
    different = term_to_lean(query["factor_difference"], declarations)
    observed = term_to_lean(query["observations_differ"], declarations)
    source = (
        "import LeanProofs\n"
        f"example : ∀ ({left} {right} : Int), {different} → {observed} → False :=\n"
        f"  ProofFormatFixture.{selected_theorem}\n"
    )
    (root / "Obligation.lean").write_text(source)
    result = subprocess.run(["lean", "-DwarningAsError=true", "Obligation.lean"], cwd=root, env=env,
                            capture_output=True, timeout=30)
    if result.returncode == 0 and not result.stderr:
        verdict = "kernel-type-checked"
    elif result.returncode == 1 and b"Type mismatch" in result.stdout:
        verdict = "obligation-type-mismatch"
    else:
        raise RuntimeError((result.returncode, result.stdout, result.stderr))
    return {"status": verdict, "obligation_sha256": digest(source.encode("utf-8"))}


def proof_receipt(wire, format_, entry, payload, checker):
    return {
        "schema": SCHEMA, "query_sha256": digest(wire.encode("utf-8")), "format": format_,
        "entry": entry, "artifact_sha256": digest(payload), "checker_subject_sha256": checker,
    }


def decide(request, supplied, payload, checked):
    if supplied.keys() != request.keys() or supplied["schema"] != SCHEMA:
        return "schema-mismatch"
    if request["format"] != supplied["format"]:
        return "format-mismatch"
    if request["query_sha256"] != supplied["query_sha256"]:
        return "query-mismatch"
    if request["entry"] != supplied["entry"]:
        return "entry-mismatch"
    if request["checker_subject_sha256"] != supplied["checker_subject_sha256"]:
        return "checker-changed"
    if request["artifact_sha256"] != supplied["artifact_sha256"] or digest(payload) != supplied["artifact_sha256"]:
        return "artifact-mismatch"
    return checked.get(digest(canonical(supplied)), "no-recorded-check")


def observe(root, env, proof, modes):
    for name in ("LeanProofs.lean", "CpcFixtures.lean"):
        shutil.copyfile(HERE / name, root / name)
    for value, payload in proof.items():
        (root / f"proof{value}.cpc").write_bytes(payload)
    axioms = execute(["lean", "-DwarningAsError=true", "-o", "LeanProofs.olean", "LeanProofs.lean"],
                     root, env=env).decode().splitlines()
    if len(axioms) != 2 or any("does not depend on any axioms" not in line for line in axioms):
        raise AssertionError(axioms)
    transcript = execute(["lean", "-DwarningAsError=true", "--run", "CpcFixtures.lean"], root, env=env)
    matrix = []
    wires = {}
    for line in transcript.decode().splitlines():
        current = json.loads(line)
        value, wire = current["literal"], current["wire"]
        wires[value] = wire
        for artifact, theorem in VALUES.items():
            lean = kernel_check(wire, theorem, root, env)
            expected_lean = "kernel-type-checked" if value == artifact else "obligation-type-mismatch"
            expected_cpc = "runtime-cpc-accepted" if value == artifact else "assumptions"
            if lean["status"] != expected_lean or current[theorem] != expected_cpc:
                raise AssertionError((value, artifact, lean, current[theorem]))
            accepted = {LEAN_FORMAT: lean, CPC_FORMAT: {"status": current[theorem]}}
            matrix.append({"query_literal": value, "artifact_literal": artifact, "checks": accepted})
            if value == artifact:
                for key, mode in modes.items():
                    receipt = proof_receipt(wire, key, mode["entry"][value],
                                            mode["payload"][value], mode["checker"])
                    mode["receipts"][value] = receipt
    if set(wires) != set(VALUES) or wires[7] == wires[8]:
        raise AssertionError("Expected two different exact queries")
    return axioms, matrix, digest(transcript)


def run(logos):
    if execute(["git", "rev-parse", "HEAD"], logos).decode().strip() != LOGOS_REV:
        raise AssertionError("Unexpected Logos checkout")
    if execute(["git", "status", "--porcelain", "--untracked-files=no"], logos):
        raise AssertionError("Logos checkout has changed tracked sources")
    library = logos / ".lake/build/lib/lean"
    api = library / "Cpc/Api.olean"
    if not api.is_file():
        raise RuntimeError("Build the pinned Logos Cpc library before replay")
    lean = execute(["lean", "--version"], ROOT).decode().strip()
    original = (SOURCE_GATE / "proof.cpc").read_bytes()
    proofs = {7: original, 8: original.replace(b" 7 ", b" 8 ")}
    archive_bytes = execute(["git", "archive", BASELINE, PROTOTYPE], ROOT)
    source_proofs = (HERE / "LeanProofs.lean").read_bytes()
    with TemporaryDirectory(prefix="llmlang-proof-formats-") as tmp:
        with tar_open(fileobj=BytesIO(archive_bytes)) as archive:
            archive.extractall(tmp, filter="data")
        root = Path(tmp) / PROTOTYPE
        env = {**os.environ, "LEAN_PATH": f".:{library}", "LC_ALL": "C"}
        modules = rebuild(root, env)
        tool = {"version": lean, "executable_sha256": digest(Path(shutil.which("lean")).read_bytes())}
        checker_contexts = {
            LEAN_FORMAT: {"lean": tool, "interpreter_sha256": digest(Path(__file__).read_bytes())},
            CPC_FORMAT: {"lean": tool, "logos_revision": LOGOS_REV, "logos_api_sha256": digest(api.read_bytes()),
                         "modules": modules, "driver_sha256": digest((HERE / "CpcFixtures.lean").read_bytes()),
                         "rebuild_sha256": digest((SOURCE_GATE / "run.py").read_bytes())},
        }
        modes = {
            LEAN_FORMAT: {"checker": digest(canonical(checker_contexts[LEAN_FORMAT])),
                          "entry": VALUES, "payload": {7: source_proofs, 8: source_proofs}, "receipts": {}},
            CPC_FORMAT: {"checker": digest(canonical(checker_contexts[CPC_FORMAT])),
                         "entry": {7: "proof", 8: "proof"}, "payload": proofs, "receipts": {}},
        }
        axioms, matrix, transcript = observe(root, env, proofs, modes)

    l7, l8 = (modes[LEAN_FORMAT]["receipts"][value] for value in VALUES)
    c7, c8 = (modes[CPC_FORMAT]["receipts"][value] for value in VALUES)
    checked = {digest(canonical(modes[format_]["receipts"][item["query_literal"]])): proof_result["status"]
               for item in matrix if item["query_literal"] == item["artifact_literal"]
               for format_, proof_result in item["checks"].items()}
    controls = (
        ("same_lean", l7, l7, source_proofs, "kernel-type-checked"),
        ("same_cpc", c7, c7, original, "runtime-cpc-accepted"),
        ("same_lean_bytes_wrong_query", l8, l7, source_proofs, "query-mismatch"),
        ("same_query_wrong_lean_entry", l7, {**l7, "entry": l8["entry"]}, source_proofs, "entry-mismatch"),
        ("relabelled_cpc_as_lean", c7, {**c7, "format": LEAN_FORMAT}, original, "format-mismatch"),
        ("different_cpc_bytes", c7, c7, proofs[8], "artifact-mismatch"),
        ("different_wire_same_format", c8, c7, original, "query-mismatch"),
        ("changed_checker", {**c7, "checker_subject_sha256": "0" * 64}, c7, original, "checker-changed"),
        ("unrecorded_checker_result", {**c7, "checker_subject_sha256": "0" * 64},
         {**c7, "checker_subject_sha256": "0" * 64}, original, "no-recorded-check"),
        ("missing_schema", c7, {k: v for k, v in c7.items() if k != "schema"}, original, "schema-mismatch"),
    )
    decisions = {}
    for name, expected, seen, payload, outcome in controls:
        state = decide(expected, seen, payload, checked)
        if state != outcome:
            raise AssertionError((name, state, outcome))
        decisions[name] = state
    receipts = [{**receipt, "receipt_key": digest(canonical(receipt)), "checker_result": checked[digest(canonical(receipt))]}
                for mode in modes.values() for receipt in mode["receipts"].values()]
    if len({receipt["receipt_key"] for receipt in receipts}) != 4:
        raise AssertionError("Receipt identity collided across subjects or formats")
    return {
        "schema": "llmlang-proof-format-comparison/1", "baseline": BASELINE,
        "python": platform.python_version(), "lean": lean, "logos_revision": LOGOS_REV,
        "sources_sha256": {name: digest((HERE / name).read_bytes())
                           for name in ("run.py", "LeanProofs.lean", "CpcFixtures.lean")},
        "reused_gate_runner_sha256": digest((SOURCE_GATE / "run.py").read_bytes()),
        "lean_proof_axioms": axioms, "cpc_transcript_sha256": transcript,
        "proof_checks": matrix, "checker_contexts": checker_contexts,
        "receipts": receipts, "reuse_controls": decisions,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logos", type=Path, required=True)
    print(json.dumps(run(parser.parse_args().logos.resolve()), indent=2))
