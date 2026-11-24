"""Replay cvc5 witnesses for the Lean-owned symbolic transition query controls."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess

from smt_adapter import PROFILE as SMT_PROFILE

ROOT = Path(__file__).resolve().parent
LEAN_COMMIT = "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9"
TIMEOUT_SECONDS = 30
NUMERAL = r"(?:0|[1-9][0-9]*)"
INTEGER = rf"({NUMERAL}|\(\s*-\s+{NUMERAL}\s*\))"
MODEL = re.compile(rf"sat\s+\(\s*\(v0\s+{INTEGER}\)\s*\(v1\s+{INTEGER}\)\s*\)\s*", re.ASCII)


def run(args, *, env=None, source=None):
    result = subprocess.run(args, env=env, input=source, capture_output=True,
                            timeout=TIMEOUT_SECONDS, check=False)
    if result.returncode or result.stderr:
        raise ValueError(f"command failed: {args[0]}: {(result.stdout + result.stderr).decode(errors='replace')}")
    return result.stdout


def parse_model(raw):
    match = MODEL.fullmatch(raw.decode("ascii"))
    if match is None:
        raise ValueError("expected exactly two ordered integer model values")
    values = []
    for term in match.groups():
        values.append(-int(term.strip("()").split()[1]) if term.startswith("(") else int(term))
    return values


def confirm_replay(raw, values):
    replay = json.loads(raw)
    x, _ = values
    expected = {
        "input": values, "observed": [[x, abs(x)], [x, 0]],
        "specified": [[x, 0], [x, 0]], "mismatch": True,
    }
    if x == 0 or json.dumps(replay, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise ValueError("solver model did not replay the intended state difference")
    return replay


def check(lean, cvc5, output):
    version = run([lean, "--version"]).decode().strip()
    if not version.startswith("Lean (version 4.36.0, ") or f"commit {LEAN_COMMIT}" not in version:
        raise ValueError("unexpected Lean version")
    solver_version = run([cvc5, "--version"]).decode().splitlines()[0]
    if solver_version != SMT_PROFILE["solver_version"]:
        raise ValueError("unexpected cvc5 version")

    env = {**os.environ, "LEAN_PATH": str(output)}
    for name in ("TransitionState", "SymbolicState", "SymbolicQuery"):
        stdout = run([lean, "-DwarningAsError=true", "-o", str(output / f"{name}.olean"),
                      str(ROOT / f"{name}.lean")], env=env)
        if stdout:
            (output / f"{name}-audit.txt").write_bytes(stdout)

    audit = output / "AxiomAudit.lean"
    audit.write_text("import SymbolicQuery\n#print axioms TransitionState.Symbolic.Query.mismatch_correct\n")
    axiom_report = run([lean, "-DwarningAsError=true", str(audit)], env=env)
    expected_report = (
        b"'TransitionState.Symbolic.Query.mismatch_correct' depends on axioms: "
        b"[propext, Classical.choice, Quot.sound]\n"
    )
    if axiom_report != expected_report:
        raise ValueError("unexpected query theorem axiom audit")
    (output / "axioms.txt").write_bytes(axiom_report)

    driver = [lean, "-DwarningAsError=true", "--run", str(ROOT / "SymbolicQuery.lean")]
    results = {}
    for name in ("absolute", "zero-all", "zero-final"):
        counterexample = name == "zero-all"
        query = run([*driver, "model" if counterexample else "query", name], env=env)
        (output / f"{name}.smt2").write_bytes(query)
        stdout = run([cvc5, "--lang=smt2"], source=query)
        (output / f"{name}-stdout.txt").write_bytes(stdout)
        result = {"query_sha256": sha256(query).hexdigest()}
        if counterexample:
            values = parse_model(stdout)
            raw = run([*driver, "replay", name, *map(str, values)], env=env)
            (output / "replay.json").write_bytes(raw)
            result.update(status="sat-replayed", witness=confirm_replay(raw, values))
        else:
            if stdout != b"unsat\n":
                raise ValueError(f"expected unsat for {name}")
            result["status"] = "unsat"
        results[name] = result

    summary = {"profile": "lean-owned-register-state-smt-v1",
               "lean": version, "cvc5": solver_version, "cases": results}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True)
    parser.add_argument("--cvc5", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=False)
        summary = check(args.lean, args.cvc5, output)
    except (OSError, ValueError, IndexError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
