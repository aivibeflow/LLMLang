"""Compare one FRET temporal export with a bounded SMT contract and a checked state model."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import subprocess

HERE = Path(__file__).resolve().parent
FRET = "58db455be35182a015e607232d9f4e3c86731932"
FRET_FINITE = "((F[0,2] posted) | (F[0,1] LAST))"
FRET_RISING = "((LAST V (((! approved) & ((! LAST) & (X approved))) -> (X ((F[0,2] posted) | (F[0,1] LAST))))) & (approved -> ((F[0,2] posted) | (F[0,1] LAST))))"


def run(*command, data=None):
    return subprocess.run(command, input=data, check=True, capture_output=True, text=True, timeout=60).stdout.strip()


def temporal(fret, solver):
    # Match the two original formula trees before using their restricted unrolling.
    assert fret["deadline"]["finite"] == FRET_FINITE
    assert fret["deadline"]["infinite"] == "(F[0,2] posted)"
    assert fret["rising_deadline"]["finite"] == FRET_RISING
    cases = []
    for length, rising in product(range(1, 6), (False, True)):
        indices = range(length) if rising else (0,)
        variables = [f"p{tick}" for tick in range(length)]
        if rising:
            variables += [f"a{tick}" for tick in range(length)]
        # X identifies the next time point, while LAST is true at the final point.
        # A guarded obligation at tick i can be excused by LAST at i or i+1.
        def term(tick, open_end):
            replies = [f"p{other}" for other in range(tick, min(tick + 3, length))]
            response = "(or " + " ".join([*replies, "true" if open_end and tick + 2 >= length else "false"]) + ")"
            if not rising:
                return response
            trigger = "a0" if tick == 0 else f"(and (not a{tick - 1}) a{tick})"
            return f"(=> {trigger} {response})"

        def expression(open_end):
            return "(and true " + " ".join(term(tick, open_end) for tick in indices) + ")"

        declarations = [f"(declare-const {name} Bool)" for name in variables]
        query = "\n".join(["(set-logic QF_LIA)", *declarations,
                           f"(assert (xor {expression(True)} {expression(False)}))", "(check-sat)", ""])
        status = run(solver, "--lang=smt2", data=query)
        mismatches = []
        for values in product((False, True), repeat=len(variables)):
            posted = values[:length]
            approval = values[length:]
            triggered = [i for i in indices if not rising or approval[i] and (i == 0 or not approval[i - 1])]
            missing = [i for i in triggered if not any(posted[i:i + 3])]
            fret_satisfies = all(length - 1 - i < 2 for i in missing)
            closed_satisfies = not missing
            if fret_satisfies != closed_satisfies:
                mismatches.append(dict(zip(variables, values)))
        assert status == ("sat" if mismatches else "unsat")
        cases.append({"ticks": length, "rising_edge": rising, "traces": 2 ** len(variables),
                      "different_verdicts": len(mismatches), "first_difference": next(iter(mismatches), None),
                      "smt_xor": status, "query_sha256": sha256(query.encode()).hexdigest()})
    return cases


def integer_contract(solver):
    valid = "(and (> amount 0) (<= amount before))"
    success_update = "(=> success (= after (- before amount)))"
    fail_frame = "(=> (not success) (= after before))"
    exact = f"(and (= success {valid}) {success_update} {fail_frame})"
    checks = {
        "matches_total_reference": f"(xor {exact} (and (= success {valid}) (= after (ite {valid} (- before amount) before))))",
        "necessity_only_misses_valid_request": f"(and (=> success {valid}) {success_update} {fail_frame} (not {exact}))",
        "sufficiency_only_allows_invalid_request": f"(and (=> {valid} success) {success_update} {fail_frame} (not {exact}))",
        "missing_failure_frame_permits_mutation": f"(and (= success {valid}) {success_update} (not {exact}))",
        "no_new_negative_balance_from_nonnegative": f"(and (>= before 0) {exact} (< after 0))",
    }
    observations = {}
    for name, assertion in checks.items():
        query = "\n".join(["(set-logic QF_LIA)", "(declare-const before Int)", "(declare-const amount Int)",
                           "(declare-const success Bool)", "(declare-const after Int)",
                           f"(assert {assertion})", "(check-sat)", ""])
        verdict = run(solver, "--lang=smt2", data=query)
        observations[name] = {"verdict": verdict, "query_sha256": sha256(query.encode()).hexdigest()}
        if verdict == "sat":
            with_model = "(set-option :produce-models true)\n" + query + "(get-value (before amount success after))\n"
            response = run(solver, "--lang=smt2", data=with_model)
            checked_status, model = response.split("\n", 1)
            assert checked_status == verdict
            observations[name]["checked_model"] = model
            observations[name]["model_query_sha256"] = sha256(with_model.encode()).hexdigest()
    assert [row["verdict"] for row in observations.values()] == ["unsat", "sat", "sat", "sat", "unsat"]
    return observations


def experiment(args):
    assert run("git", "-C", args.fret_root, "rev-parse", "HEAD") == FRET
    assert not run("git", "-C", args.fret_root, "diff", "--name-only", "HEAD")
    fret = json.loads(run(args.node, HERE / "fret.cjs", args.fret_root))
    assert Counter(row["outcome"] for row in fret.values()) == {
        "formalized": 6, "parse-error": 1, "saved-without-formula": 1,
    }
    assert "old" in fret["old_call"]["variables"]
    assert "(F " in fret["old_call"]["infinite"]
    paths = ("Withdrawal.lean", "fret.cjs", "package-lock.json", "package.json", "requirements.json", "run.py")
    return {
        "schema": "rt02-requirement-backend-comparison-v1",
        "fret_commit": FRET,
        "tool_versions": {"python": platform.python_version(), "node": run(args.node, "--version"),
                          "cvc5": run(args.cvc5, "--version").splitlines()[0], "lean": run(args.lean, "--version")},
        "source_sha256": {path: sha256((HERE / path).read_bytes()).hexdigest() for path in paths},
        "fret": fret,
        "finite_temporal": temporal(fret, args.cvc5),
        "integer_contract": integer_contract(args.cvc5),
        "lean_axiom_audit": run(args.lean, "-DwarningAsError=true", HERE / "Withdrawal.lean").splitlines(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fret-root", type=Path, required=True)
    parser.add_argument("--node", default="node")
    parser.add_argument("--cvc5", required=True)
    parser.add_argument("--lean", required=True)
    args = parser.parse_args()
    print(json.dumps(experiment(args), indent=2, sort_keys=True))
