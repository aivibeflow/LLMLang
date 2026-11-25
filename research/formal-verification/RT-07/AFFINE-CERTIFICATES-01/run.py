#!/usr/bin/env python3
"""Bypass the CPC checker for a closed affine profile with Lean-checked certificates."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from normalize import Unsupported, assertion, lean, normalize, weight_witness

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE.parents[1] / "PROOF-OBLIGATION-BENCHMARK" / "symbolic-smt-results"
EXPECTED = {
    "absolute": ("absolute.smt2", "ac59fcb856a5aaff9457c250f2cb9ef24aa193bd7ddd8b600a7c508265481aad"),
    "zeroFinal": ("zero-final.smt2", "7fa87d636df3ba15da913ca2028a579dad3794c7fd248c5b50daf9ca232aafc4"),
}
WEIGHTED = "(and (<= (+ v0 v1) 0) (<= 2 (+ (+ v0 v0) (+ v1 v1))))"
CONTROLS = {
    "weighted": WEIGHTED,
    "oneFeasibleBranch": f"(or {WEIGHTED} (and (<= v0 0) (<= 0 v1)))",
    "integerOnly": "(= (+ v0 v0) 1)",
}


def digest(content):
    return sha256(content).hexdigest()


def query(body):
    return ("(set-logic QF_LIA)\n(declare-const v0 Int)\n(declare-const v1 Int)\n"
            f"(assert {body})\n(check-sat)\n(exit)\n")


def check_version(tool, marker):
    text = subprocess.check_output([tool, "--version"], text=True, timeout=10).splitlines()[0]
    if marker not in text:
        raise ValueError(f"Unpinned tool {text}")
    return text


def solve(solver, text):
    checked = subprocess.run([solver, "--lang=smt2"], input=text, text=True, capture_output=True,
                             timeout=30, check=True)
    if checked.stderr or checked.stdout.strip() not in {"sat", "unsat"}:
        raise RuntimeError(f"Unexpected comparison result {checked}")
    return checked.stdout.strip()


def branch_literal(branch):
    return "[" + ", ".join("⟨" + ", ".join(map(str, row)) + "⟩" for row in branch) + "]"


def render_branches(branches):
    return "[" + ", ".join(map(branch_literal, branches)) + "]"


def case_decisions(guards):
    return " ".join(f"by_cases h{index} : {lean(guard)} <;>" for index, guard in enumerate(guards))


def normalize_proof(name, formula, rows, guards, result, weights):
    goal = f"{name}Goal"
    branches = f"{name}Branches"
    certs = f"{name}Weights"
    hints = "".join(f", h{index}" for index in range(len(guards)))
    split = case_decisions(guards)

    expression = lean(formula)
    binders = " ".join(symbol if re.search(rf"\b{symbol}\b", expression) else f"_{symbol}"
                       for symbol in ("x", "y"))
    declarations = [
        f"def {goal} ({binders} : Int) : Prop := {expression}",
        f"def {branches} : List (List Row) := {render_branches(rows)}",
        f"theorem {name}Coverage (x y : Int) : {goal} x y ↔ possible x y {branches} := by\n"
        f"  {split}\n  simp [{goal}, {branches}, possible, holds, Affine.eval{hints}] <;> omega",
    ]
    audited = [f"{name}Coverage"]
    if all(weight is not None for weight in weights):
        declarations.extend([
            f"def {certs} : List (List Nat) := {json.dumps(weights)}",
            f"theorem {name}Certified (x y : Int) : ¬ {goal} x y := by\n"
            f"  intro claim\n  exact branches_sound x y {branches} {certs} "
            f"(by decide) (({name}Coverage x y).mp claim)",
        ])
        audited.append(f"{name}Certified")

    if result == "unsat":
        declarations.append(f"theorem {name}Direct (x y : Int) : ¬ {goal} x y := by\n"
                            f"  {split}\n  simp [{goal}{hints}] <;> omega")
        audited.append(f"{name}Direct")
    else:
        declarations.append(f"theorem {name}Witness : {goal} 0 0 := by simp [{goal}]")
        audited.append(f"{name}Witness")

    if name == "oneFeasibleBranch":
        chosen, chosen_certificate = next((row, weight) for row, weight in zip(rows, weights, strict=True)
                                          if weight is not None)
        limited_rows = render_branches([chosen])
        limited_weights = json.dumps([chosen_certificate])
        declarations.extend([
            f"theorem completeRowsRejectIncompleteWeights : "
            f"checkBranches {branches} {limited_weights} = false := by decide",
            f"theorem omittedFeasibleBranchPassesFlatCheck : "
            f"checkBranches {limited_rows} {limited_weights} = true := by decide",
            f"theorem omittedFeasibleBranchChangesCoverage : "
            f"¬ ({goal} 0 0 ↔ possible 0 0 {limited_rows}) := by\n"
            f"  simp [{goal}, possible, holds, Affine.eval]",
        ])
        audited.extend(("completeRowsRejectIncompleteWeights", "omittedFeasibleBranchPassesFlatCheck",
                        "omittedFeasibleBranchChangesCoverage"))
    return declarations, audited


def inspect_source(path, cvc5):
    raw = path.read_bytes() if isinstance(path, Path) else path.encode()
    text = raw.decode()
    formula = assertion(text)
    rows, guards = normalize(formula)
    if len(guards) > 4 or len(rows) > 64:
        raise Unsupported("Query exceeds the admitted replay bound")
    weights = [weight_witness(branch) for branch in rows]
    solver = solve(cvc5, text)
    if solver == "sat" and all(weight is not None for weight in weights):
        raise AssertionError("Certificate generation contradicted the comparison solver")
    return formula, rows, guards, weights, solver, digest(raw)


def build_module(source, lean_tool):
    with TemporaryDirectory(prefix="llmlang-affine-proof-") as temporary:
        root = Path(temporary)
        shutil.copy(HERE / "Affine.lean", root / "Affine.lean")
        (root / "Generated.lean").write_text(source, encoding="utf-8")
        check = [lean_tool, "-DwarningAsError=true"]
        env = {**os.environ, "LEAN_PATH": str(root)}
        for args in (("-o", "Affine.olean", "Affine.lean"), ("Generated.lean",)):
            completed = subprocess.run([*check, *args], cwd=root, env=env, text=True,
                                       capture_output=True, timeout=120, check=False)
            if completed.returncode or completed.stderr:
                raise RuntimeError(completed.stdout + completed.stderr)
        return completed.stdout


def replay(lean_tool, cvc5):
    lean_version = check_version(lean_tool, "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9")
    solver_version = check_version(cvc5, "1.4.2 [git 282d5e0")
    declarations = ["import Affine", "open Affine", "set_option maxHeartbeats 5000000"]
    audited = ["Affine.sound", "Affine.branches_sound"]
    record = {}
    sources = {name: ARCHIVE / filename for name, (filename, _) in EXPECTED.items()}
    sources.update({name: query(body) for name, body in CONTROLS.items()})
    for name, source in sources.items():
        formula, rows, guards, weights, solver, identity = inspect_source(source, cvc5)
        if name in EXPECTED and identity != EXPECTED[name][1]:
            raise ValueError(f"Unexpected archived content for {name}")
        definitions, theorems = normalize_proof(name, formula, rows, guards, solver, weights)
        audited.extend(theorems)
        declarations.extend(definitions)
        record[name] = {
            "query_sha256": identity, "archived": name in EXPECTED,
            "cvc5": solver, "affine": "checked_refutation" if None not in weights else "unknown",
            "branches": [{"affine_rows": branch, "weights": witness}
                         for branch, witness in zip(rows, weights, strict=True)],
        }

    unsupported = {
        "nonlinear_product": query("(<= (* v0 v1) 1)"),
        "unexpected_binder": query("(= v0 0)").replace("(declare-const v1 Int)", "(declare-const v2 Int)"),
    }
    for name, source in unsupported.items():
        try:
            normalize(assertion(source))
        except Unsupported:
            continue
        raise AssertionError(f"Accepted unsupported control {name}")

    declarations.extend(f"#print axioms {name}" for name in audited)
    generated = "\n\n".join(declarations) + "\n"
    output = build_module(generated, lean_tool)
    pattern = re.compile(r"^'([^']+)' (?:does not depend on any axioms|depends on axioms: \[(.*)\])$")
    axioms = {}
    for line in output.splitlines():
        match = pattern.fullmatch(line)
        if match is None:
            raise ValueError(f"Unexpected Lean result {line!r}")
        name, values = match.groups()
        axioms[name] = values.split(", ") if values else []
    assert list(axioms) == audited
    standard = {"propext", "Classical.choice", "Quot.sound"}
    assert all(set(values) <= standard for values in axioms.values())
    return {
        "schema": "llmlang-affine-certificate/1", "lean": lean_version, "cvc5": solver_version,
        "python": sys.version.split()[0],
        "replay_sha256": {name: digest((HERE / name).read_bytes())
                          for name in ("Affine.lean", "normalize.py", "run.py")},
        "generated_lean_sha256": digest(generated.encode()),
        "theorems": axioms, "queries": record, "unsupported": unsupported,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", default="lean")
    parser.add_argument("--cvc5", default="cvc5")
    args = parser.parse_args()
    print(json.dumps(replay(args.lean, args.cvc5), indent=2))


if __name__ == "__main__":
    main()
