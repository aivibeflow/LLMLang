"""Obtain and check CPC proofs for the two archived Lean-owned UNSAT queries."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from smt_adapter import PROFILE as SMT_PROFILE

LOGOS = (Path(__file__).resolve().parents[3]
         / "PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding")
SOURCE_DIGESTS = {
    "absolute": "ac59fcb856a5aaff9457c250f2cb9ef24aa193bd7ddd8b600a7c508265481aad",
    "zero-final": "7fa87d636df3ba15da913ca2028a579dad3794c7fd248c5b50daf9ca232aafc4",
}
AXIOMS = (
    b"'LLMLang.SymbolicCpcCertificate.BoundCertificate.ordinary_correct' depends on axioms: "
    b"[propext, Classical.choice, Quot.sound]\n"
)
TIMEOUT_SECONDS = 30


def execute(args, source=None):
    return subprocess.run(args, cwd=LOGOS, input=source, capture_output=True,
                          timeout=TIMEOUT_SECONDS, check=False)


def successful(result):
    if result.returncode or result.stderr:
        raise ValueError((result.stdout + result.stderr).decode(errors="replace"))
    return result.stdout


def run(lake, cvc5, queries, output):
    version = successful(execute([cvc5, "--version"])).decode().splitlines()[0]
    if version != SMT_PROFILE["solver_version"]:
        raise ValueError("unexpected cvc5 version")
    lean = [lake, "env", "lean", "-DwarningAsError=true"]
    lean_version = successful(execute([lake, "env", "lean", "--version"])).decode().strip()
    if (not lean_version.startswith("Lean (version 4.36.0, ")
            or "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9" not in lean_version):
        raise ValueError("unexpected Lean version")
    driver = [*lean, "--run", "SymbolicCpcCertificate.lean"]
    results = {}
    raw_files = {}
    for case, expected_hash in SOURCE_DIGESTS.items():
        source_path = queries / f"{case}.smt2"
        source = source_path.read_bytes()
        if sha256(source).hexdigest() != expected_hash:
            raise ValueError(f"unexpected source query bytes for {case}")
        raw = successful(execute([cvc5, "--lang=smt2", "--produce-proofs",
                                  "--proof-format-mode=cpc", "--dump-proofs"], source))
        raw_file = output / f"{case}-cvc5.txt"
        raw_file.write_bytes(raw)
        raw_files[case] = raw_file
        result = successful(execute([*driver, str(source_path), str(raw_file)]))
        if result != b"source-bound Logos verdict: correct\n":
            raise ValueError(f"unexpected Logos result for {case}")
        results[case] = {"source_sha256": expected_hash, "certificate_stdout_sha256": sha256(raw).hexdigest(),
                         "verdict": "correct"}

    sat_file = output / "sat-control.txt"
    sat_file.write_bytes(b"sat\n")
    source_used = output / "source-using-v1.smt2"
    original = (queries / "absolute.smt2").read_text().splitlines()
    source_used.write_text("\n".join("(assert (= v1 v1))" if line.startswith("(assert ")
                                     else line for line in original) + "\n")
    controls = [
        ("wrong-certificate", queries / "absolute.smt2", raw_files["zero-final"],
         "CPC assumptions differ from the exact source assertion"),
        ("sat-without-certificate", queries / "absolute.smt2", sat_file,
         "expected exactly one UNSAT result and one CPC command list"),
        ("used-omitted-declaration", source_used, raw_files["absolute"],
         "the second declared input occurs in the source assertion"),
    ]
    for name, query, proof, expected in controls:
        result = execute([*driver, str(query), str(proof)])
        diagnostic = (result.stdout + result.stderr).decode()
        if not result.returncode or expected not in diagnostic:
            raise ValueError(f"{name} did not fail at the expected boundary")
        (output / f"{name}-diagnostic.txt").write_text(diagnostic)

    audit = output / "AxiomAudit.lean"
    audit.write_text("import SymbolicCpcCertificate\n"
                     "#print axioms LLMLang.SymbolicCpcCertificate.BoundCertificate.ordinary_correct\n")
    axioms = successful(execute([*lean, str(audit)]))
    if b" ".join(axioms.split()) != AXIOMS.rstrip(b"\n"):
        raise ValueError("unexpected certificate binding theorem axiom audit")
    (output / "axioms.txt").write_bytes(axioms)

    summary = {"profile": "source-bound-symbolic-cpc-v1", "lean": lean_version, "cvc5": version,
               "logos_revision": "cf18742973861b3718d04c5f25775448098ff474",
               "cases": results, "controls": {name: reason for name, _, _, reason in controls}}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cvc5", required=True)
    parser.add_argument("--lake", required=True)
    parser.add_argument("--queries", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=False)
        summary = run(args.lake, args.cvc5, args.queries.resolve(), output)
    except (OSError, ValueError, IndexError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
