#!/usr/bin/env python3
"""Check declaration and parser boundaries of the pinned checked-add binding."""

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "compiler-and-translation" / "PROTOTYPES" / "LLVM-PRESERVATION-01"
sys.path.insert(0, str(FIXTURE))
import checked_add_certificate_replay as original

U32_A = "(declare-const a (_ BitVec 32))"
U33_A = "(declare-const a (_ BitVec 33))"
EXTRA = "(declare-const extra (_ BitVec 32))\n"


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Expected exactly one {old!r}")
    return text.replace(old, new, 1)


def build_query(args, archive):
    source = original.SOURCE.replace("operation", "checked_sadd")
    ir = original.lower((original.compile_source(source),))
    optimized = original.checked(
        [args.opt, "-passes=verify,default<O0>,verify", "-S", "-o", "-", "-"], source=ir,
    )
    query = original.smt_query(original.disagreement(original.paths(optimized), original.COMPONENTS))
    expected = archive["certificates"]["O0"]
    if original.digest(optimized) != expected["ir_sha256"] or original.digest(query) != expected["smt_sha256"]:
        raise ValueError("O0 IR or query bytes differ from the archive")
    return query


def run(args):
    archive = json.loads((FIXTURE / "checked-add-certificate-results.json").read_text(encoding="utf-8"))
    revision = original.checked(["git", "rev-parse", "HEAD"], cwd=args.checkout).strip()
    changes = original.checked(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=args.checkout,
    ).strip()
    lean = original.checked(["lean", "--version"]).strip()
    cvc5 = original.checked([args.cvc5, "--version"]).splitlines()[0]
    if revision != archive["logos_revision"] or changes or lean != archive["lean"] or cvc5 != archive["cvc5"]:
        raise ValueError("Expected the pinned Logos sources and tool versions")
    query = build_query(args, archive)
    with TemporaryDirectory(prefix="llmlang-rt13-cpc-declarations-") as directory:
        root = Path(directory)
        query_path = root / "query.smt2"
        proof_path = root / "proof.cpc"
        query_path.write_text(query, encoding="utf-8")
        raw = original.checked(
            [args.cvc5, "--dump-proofs", "--proof-format-mode=cpc",
             "--proof-granularity=dsl-rewrite", query_path],
        )
        proof = original.flat_proof(raw)
        if original.digest(proof) != archive["certificates"]["O0"]["cpc_sha256"]:
            raise ValueError("O0 CPC proof differs from the archive")
        logic, first, second, third, body = query.split("\n", 4)
        if [first, second, third] != [U32_A, "(declare-const b (_ BitVec 32))",
                                     "(declare-const enabled (_ BitVec 32))"]:
            raise ValueError("Unexpected source declaration order")
        proof_header = proof.splitlines(keepends=True)
        if not all(line.startswith("(declare-const ") for line in proof_header[:3]):
            raise ValueError("Expected three initial proof declarations")

        cases = (
            ("permuted_source_declarations", "\n".join((logic, third, second, first, body)), proof,
             "correct", 0),
            ("widened_source_declaration", replace_once(query, U32_A, U33_A), proof,
             "invalid-source-declarations", 3),
            ("widened_proof_declaration", query, replace_once(proof, U32_A, U33_A),
             "declarations-mismatch", 3),
            ("extra_initial_proof_declaration", query, "".join(proof_header[:3]) + EXTRA + "".join(proof_header[3:]),
             "declarations-mismatch", 3),
            ("extra_late_proof_declaration", query, proof + EXTRA, "unsupported-proof-command", 3),
        )
        results = {}
        for name, source_text, proof_text, expected, status in cases:
            query_path.write_text(source_text, encoding="utf-8")
            proof_path.write_text(proof_text, encoding="utf-8")
            attempt = original.execute(
                ["lake", "env", "lean", "-DwarningAsError=true", "--run",
                 FIXTURE / "CheckedAddCertificate.lean", query_path, proof_path],
                cwd=args.checkout,
            )
            verdict = attempt.stdout.strip()
            if (attempt.returncode, verdict) != (status, expected) or attempt.stderr:
                raise RuntimeError(f"{name}: unexpected result {attempt.returncode} {verdict!r} {attempt.stderr}")
            results[name] = {
                "smt_sha256": original.digest(source_text),
                "cpc_sha256": original.digest(proof_text),
                "exit_code": attempt.returncode,
                "bound_verdict": verdict,
            }
    return {"schema": "llmlang-rt13-cpc-declaration-controls/1", "cases": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--opt", default="opt-19")
    parser.add_argument("--cvc5", default="cvc5")
    print(json.dumps(run(parser.parse_args()), indent=2))
