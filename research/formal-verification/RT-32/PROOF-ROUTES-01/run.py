#!/usr/bin/env python3
"""Compare exact Lean obligations, reusable proofs and SMT triage."""

from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
VARIABLES = ("x", "y", "n")
ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}

# Each declaration is (premises, conclusion, typed proof reuse candidate).
CLAIMS = {
    "decrease_stride_one": (((1, "<=", "x"),), (("-", "x", 1), "<", "x"),
                            "exact decreases x 1 (by decide)"),
    "decrease_stride_two": (((2, "<=", "x"),), (("-", "x", 2), "<", "x"),
                            "exact decreases x 2 (by decide)"),
    "stays_nonnegative": (((1, "<=", "x"),), (0, "<=", ("-", "x", 1)),
                          "exact staysNonnegative x 1 h0"),
    "conserves": (((("+", "x", "y"), "=", "n"),),
                  (("+", ("-", "x", 1), ("+", "y", 1)), "=", "n"),
                  "exact transferConserves x y n 1 h0"),
    "initializes": ((("x", "=", "n"), ("y", "=", 0)), (("+", "x", "y"), "=", "n"),
                    "exact initializes x y n h0 h1"),
    "exits": (((("+", "x", "y"), "=", "n"), ("x", "=", 0)), ("y", "=", "n"),
              "exact exits x y n h0 h1"),
    "zero_decrease": (((0, "<=", "x"),), ("x", "<", "x"),
                      "exact decreases x 0 (by decide)"),
    "missing_invariant": ((("x", "=", 0),), ("y", "=", "n"),
                           "exact exits x y n h0 h0"),
    "weakened_guard": (((0, "<=", "x"),), (0, "<=", ("-", "x", 1)),
                       "exact staysNonnegative x 1 h0"),
    "extra_update": (((("+", "x", "y"), "=", "n"),),
                     (("+", ("-", "x", 1), ("+", "y", 2)), "=", "n"),
                     "exact transferConserves x y n 1 h0"),
}


def term(value, fmt):
    if isinstance(value, (int, str)):
        return str(value)
    op, left, right = value
    a, b = term(left, fmt), term(right, fmt)
    return f"({op} {a} {b})" if fmt == "smt" else f"({a} {op} {b})"


def relation(value, fmt):
    left, op, right = value
    a, b = term(left, fmt), term(right, fmt)
    if fmt == "smt":
        return f"({op} {a} {b})"
    return f"{a} {op.replace('<=', '≤')} {b}"


def value(expr, assignment):
    if isinstance(expr, int):
        return expr
    if isinstance(expr, str):
        return assignment[expr]
    op, left, right = expr
    a, b = value(left, assignment), value(right, assignment)
    return a + b if op == "+" else a - b


def holds(statement, assignment):
    left, op, right = statement
    a, b = value(left, assignment), value(right, assignment)
    return {"<": a < b, "<=": a <= b, "=": a == b}[op]


def smt_query(premises, conclusion):
    lines = ["(set-logic QF_LIA)", "(set-option :produce-models true)"]
    lines.extend(f"(declare-const {var} Int)" for var in VARIABLES)
    lines.extend(f"(assert {relation(hypothesis, 'smt')})" for hypothesis in premises)
    lines.append(f"(assert (not {relation(conclusion, 'smt')}))")
    lines.append("(check-sat)")
    return "\n".join(lines) + "\n"


def solve(commands, query, premises, conclusion):
    results = {}
    for label, command in commands.items():
        verdict = subprocess.run(command, input=query, text=True, capture_output=True, check=True)
        status = verdict.stdout.strip()
        if verdict.stderr or status not in {"unsat", "sat"}:
            raise AssertionError((label, verdict.stdout, verdict.stderr))
        results[label] = {"status": status}
        if status == "sat":
            ask = query + "(get-value (x y n))\n"
            run = subprocess.run(command, input=ask, text=True, capture_output=True, check=True)
            pairs = re.findall(r"\(([xyn])\s+(\(-\s+\d+\)|\d+)\)", run.stdout)
            model = {name: (-int(raw[2:-1]) if raw.startswith("(-") else int(raw))
                     for name, raw in pairs}
            if not (set(model) == set(VARIABLES) and all(holds(h, model) for h in premises)
                    and not holds(conclusion, model)):
                raise AssertionError((label, run.stdout, model))
            results[label]["validated_witness"] = model
    if len({item["status"] for item in results.values()}) != 1:
        raise AssertionError(results)
    return results


def signature(premises, conclusion, *, use_names=True):
    args = " ".join(f"(h{i} : {relation(hypothesis, 'lean')})"
                    if use_names else f"({relation(hypothesis, 'lean')}) →"
                    for i, hypothesis in enumerate(premises))
    return (f"(x y n : Int) {args} : {relation(conclusion, 'lean')}" if use_names else
            f": ∀ (x y n : Int), {args} {relation(conclusion, 'lean')}")


def check_lean(directory, lean, premises, conclusion, route, tactic):
    args = signature(premises, conclusion)
    header = "import ArithmeticRules\nset_option linter.unusedVariables false\n"
    if route == "foreign_premise":
        header += f"axiom foreignClaim {signature(premises, conclusion, use_names=False)}\n"
    source = header + f"theorem claim {args} := by\n  {tactic}\n#print axioms claim\n"
    path = directory / "Claim.lean"
    path.write_text(source)
    result = subprocess.run([lean, "-DwarningAsError=true", path.name], cwd=directory,
                            env={**os.environ, "LEAN_PATH": str(directory)}, text=True,
                            capture_output=True)
    status, axioms = "lean_rejected", []
    if result.returncode == 0:
        match = re.search(r"depends on axioms: \[([^\]]*)\]", result.stdout)
        if match:
            axioms = match.group(1).split(", ")
        elif "does not depend on any axioms" not in result.stdout:
            raise AssertionError(result.stdout)
        status = "checked" if set(axioms) <= ALLOWED_AXIOMS else "unapproved_axiom"
    return {"status": status, "axioms": axioms,
            "generated_sha256": sha256(source.encode()).hexdigest()}


def compare():
    lean = os.environ.get("LEAN", "lean")
    commands = {
        "cvc5": [os.environ.get("CVC5", "cvc5"), "--lang=smt2"],
        "z3": [os.environ.get("Z3", "z3"), "-in", "-smt2"],
    }
    counts = Counter()
    rows = {}
    with tempfile.TemporaryDirectory() as build:
        directory = Path(build)
        lemmas = directory / "ArithmeticRules.lean"
        lemmas.write_bytes((HERE / lemmas.name).read_bytes())
        subprocess.run([lean, "-DwarningAsError=true", "-o", "ArithmeticRules.olean", lemmas.name],
                       cwd=directory, check=True)
        for name, (premises, conclusion, reused) in CLAIMS.items():
            query = smt_query(premises, conclusion)
            solvers = solve(commands, query, premises, conclusion)
            admissible = solvers["cvc5"]["status"] == "unsat"
            routes = {"simp": "simp_all", "omega": "omega", "reuse": reused}
            if admissible:
                routes["solver_triage_then_kernel"] = "omega"
            if name == "zero_decrease":
                arguments = " ".join(f"h{i}" for i in range(len(premises)))
                routes["foreign_premise"] = f"exact foreignClaim x y n {arguments}"
                routes["placeholder"] = "sorry"
            record = {}
            for route, tactic in routes.items():
                record[route] = check_lean(directory, lean, premises, conclusion, route, tactic)
                counts[f"{route}/{record[route]['status']}"] += 1
            if (record["omega"]["status"] == "checked") != admissible:
                raise AssertionError((name, record, solvers))
            if admissible and record["reuse"]["status"] != "checked":
                raise AssertionError((name, record))
            if "foreign_premise" in record:
                assert record["foreign_premise"]["status"] == "unapproved_axiom"
                assert record["placeholder"]["status"] == "lean_rejected"
            counts["solver_sat" if not admissible else "solver_unsat"] += 1
            rows[name] = {"smt_assumptions_sha256": sha256(query.encode()).hexdigest(),
                          "solvers": solvers, "proof_routes": record}
    versions = {label: subprocess.check_output([command[0], "--version"], text=True).splitlines()[0]
                for label, command in commands.items()}
    versions["lean"] = subprocess.check_output([lean, "--version"], text=True).strip()
    return {
        "schema": "llmlang-proof-route-comparison/1", "python": platform.python_version(),
        "tools": versions, "approved_axioms": sorted(ALLOWED_AXIOMS),
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "ArithmeticRules.lean")},
        "counts": counts, "obligations": rows,
    }


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2, sort_keys=True))
