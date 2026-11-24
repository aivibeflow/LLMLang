#!/usr/bin/env python3
"""Bind cvc5 CPC certificates to the exact checked-add mismatch formulas."""

import argparse
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

from checked_add_formula import disagreement, paths, smt_query
from checked_add_replay import COMPONENTS, digest
from integer_fixture import SOURCE, compile_source
from llvm_integer_probe import lower


HERE = Path(__file__).resolve().parent
LOGOS_REVISION = "cf18742973861b3718d04c5f25775448098ff474"
LEAN_REVISION = "293d5d0c0c3f3dded4688b3ccd6a33939ac5102b"
CVC5_VERSION = "cvc5 1.4.2 [git 282d5e0"


def execute(command, *, cwd=None, source=None, timeout=60):
    return subprocess.run(command, cwd=cwd, input=source, text=True, capture_output=True, timeout=timeout)


def checked(command, **kwargs):
    completed = execute(command, **kwargs)
    if completed.returncode:
        raise ValueError(f"{command} failed: {completed.stdout}\n{completed.stderr}")
    return completed.stdout


def flat_proof(output):
    lines = output.splitlines(keepends=True)
    if len(lines) < 4 or [line.strip() for line in (lines[0], lines[1], lines[-1])] != ["unsat", "(", ")"]:
        raise ValueError("Expected cvc5 UNSAT and one wrapped proof")
    return "".join(lines[2:-1])


def check_compiled(logo, proof, expected):
    result = execute([logo, proof])
    if result.returncode != {"correct": 0, "incorrect": 1}[expected] or result.stdout.strip() != expected:
        raise ValueError(f"Unexpected compiled Logos result: {result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def check_bound(checkout, query, proof, expected):
    result = execute(["lake", "env", "lean", "-DwarningAsError=true", "--run",
                      HERE / "CheckedAddCertificate.lean", query, proof], cwd=checkout)
    statuses = {"correct": 0, "incorrect": 1, "assumptions-mismatch": 3, "declarations-mismatch": 3}
    if result.returncode != statuses[expected] or result.stdout.strip() != expected:
        raise ValueError(f"Unexpected bound checker result: {result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def replay(opt, cvc5, checkout):
    revision = checked(["git", "rev-parse", "HEAD"], cwd=checkout).strip()
    if revision != LOGOS_REVISION or checked(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=checkout,
    ).strip():
        raise ValueError("Expected the clean pinned Logos revision")
    lean = checked(["lean", "--version"], cwd=checkout).strip()
    version = checked([cvc5, "--version"]).splitlines()[0]
    if LEAN_REVISION not in lean or not version.startswith(CVC5_VERSION):
        raise ValueError(f"Expected the pinned Lean and cvc5 versions, got {lean} and {version}")
    checked(["bash", "scripts/build.sh", "logos"], cwd=checkout, timeout=1800)
    logo = checkout / ".lake" / "build" / "bin" / "logos"
    initial_ledger = json.loads((HERE / "checked-add-results.json").read_text(encoding="utf-8"))
    source = SOURCE.replace("operation", "checked_sadd")
    unoptimized = lower((compile_source(source),))
    if digest(source) != initial_ledger["source_sha256"] or digest(unoptimized) != initial_ledger["unoptimized_ir_sha256"]:
        raise ValueError("The checked-add source or initial IR changed")
    with TemporaryDirectory(prefix="llmlang-checked-add-cpc-") as tmp:
        work = Path(tmp)
        receipts = {}
        artifacts = {}
        for level in (0, 3):
            label = f"O{level}"
            ir = checked([opt, f"-passes=verify,default<{label}>,verify", "-S", "-o", "-", "-"],
                         source=unoptimized)
            exact = initial_ledger["modules"]["preserving"][label]
            query = smt_query(disagreement(paths(ir), COMPONENTS))
            if digest(ir) != exact["ir_sha256"] or digest(query) != exact["complete_mismatch"]["sha256"]:
                raise ValueError(f"The exact {label} IR or complete mismatch formula changed")
            query_path, proof_path = work / f"{label}.smt2", work / f"{label}.cpc"
            query_path.write_text(query, encoding="utf-8")
            raw = checked([cvc5, "--dump-proofs", "--proof-format-mode=cpc", "--proof-granularity=dsl-rewrite",
                           query_path])
            proof = flat_proof(raw)
            proof_path.write_text(proof, encoding="utf-8")
            receipts[label] = {
                "ir_sha256": digest(ir),
                "smt_sha256": digest(query),
                "cvc5_stdout_sha256": digest(raw),
                "cpc_sha256": digest(proof),
                "proof_steps": sum(line.startswith("(step ") for line in proof.splitlines()),
                "compiled_verdict": check_compiled(logo, proof_path, "correct"),
                "bound_verdict": check_bound(checkout, query_path, proof_path, "correct"),
            }
            artifacts[label] = query_path, proof_path

        query, proof_path = artifacts["O0"]
        proof = proof_path.read_text(encoding="utf-8")
        renamed = re.sub(r"(?<=[( \n])a(?=[) \n])", "other_input", proof)
        if renamed == proof:
            raise ValueError("The rename control did not modify the proof")
        lines = proof.splitlines(keepends=True)
        if " false :rule " not in lines[-1]:
            raise ValueError("Expected an explicit false final conclusion")
        lines[-1] = lines[-1].replace(" false :rule ", " true :rule ", 1)
        corrupted = "".join(lines)
        changed = {}
        for name, text, plain, bound in (
            ("renamed_input", renamed, "correct", "declarations-mismatch"),
            ("corrupted_conclusion", corrupted, "incorrect", "incorrect"),
        ):
            path = work / f"{name}.cpc"
            path.write_text(text, encoding="utf-8")
            changed[name] = {"cpc_sha256": digest(text), "compiled_verdict": check_compiled(logo, path, plain),
                             "bound_verdict": check_bound(checkout, query, path, bound)}
        for target, other in (("O0", "O3"), ("O3", "O0")):
            changed[f"{other}_certificate_for_{target}"] = {
                "compiled_verdict": receipts[other]["compiled_verdict"],
                "bound_verdict": check_bound(checkout, artifacts[target][0], artifacts[other][1],
                                             "assumptions-mismatch"),
            }
    return {"schema": "llmlang-rt13-checked-add-cpc-v1", "logos_revision": revision,
            "lean": lean, "cvc5": version, "certificates": receipts, "controls": changed}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--opt", default="opt-19")
    parser.add_argument("--cvc5", default="cvc5")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = replay(args.opt, args.cvc5, args.checkout.resolve())
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
