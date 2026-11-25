"""Run deterministic work-budget controls on three SMT query families."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PROTOTYPE = HERE.parents[2] / "PROTOTYPES" / "RT-04-01"
sys.path.insert(0, str(PROTOTYPE))

from rt03_feasibility_outcomes import SolverAnswer, classify_solver_answer, retain_as_possible

BASELINE = "9358f4b731b7f0b058deb1ef0a827edebfe43b12"
SIZES = (4, 8, 16, 32)
LIMITS = (1, 100, 10_000, 100_000)
FAMILIES = ("difference-cycle", "pigeonhole", "weighted-subset")
HOST_DEADLINE_SECONDS = 5


def query(family, size, expected):
    count = size + int(family == "pigeonhole" and expected == "unsat")
    variables = [f"x{index}" for index in range(count)]
    sort = "Bool" if family == "weighted-subset" else "Int"
    assertions = []
    if family == "difference-cycle":
        assertions = [f"(<= (+ {left} 1) {right})" for left, right in zip(variables, variables[1:])]
        assertions.append(f"(<= {variables[-1]} (+ {variables[0]} {size - (2 if expected == 'unsat' else 1)}))")
    elif family == "pigeonhole":
        assertions = [f"(and (<= 0 {name}) (< {name} {size}))" for name in variables]
        assertions.append("(distinct " + " ".join(variables) + ")")
    else:
        weights = [2 * (409 + index * index + 17 * index) for index in range(count)]
        target = sum(weights[::2]) + int(expected == "unsat")
        terms = " ".join(f"(ite {name} {weight} 0)" for name, weight in zip(variables, weights))
        assertions.append(f"(= (+ {terms}) {target})")
    return "\n".join(["(set-logic QF_LIA)",
                      *(f"(declare-const {name} {sort})" for name in variables),
                      *(f"(assert {term})" for term in assertions), "(check-sat)", ""])


def invoke(command, formula, deadline):
    try:
        result = subprocess.run(command, input=formula, capture_output=True, text=True, timeout=deadline)
    except subprocess.TimeoutExpired:
        return "unknown", "host-deadline"
    if result.returncode != 0 or result.stderr.strip():
        raise ValueError((command, result.returncode, result.stdout, result.stderr))
    return result.stdout.strip(), None


def classify(backend, executable, formula, limit):
    args = ([executable, "--lang=smt2", f"--rlimit={limit}"] if backend == "cvc5"
            else [executable, "-in", "-smt2", f"rlimit={limit}"])
    status, reason = invoke(args, formula, HOST_DEADLINE_SECONDS)
    if status == "unknown" and reason is None:
        diagnostic, deadline = invoke(args, formula + "(get-info :reason-unknown)\n", HOST_DEADLINE_SECONDS)
        if deadline is not None:
            return "unknown", deadline
        first, reason = diagnostic.split("\n", 1)
        assert first == status and reason.startswith("(:reason-unknown")
    assert status in {"sat", "unsat", "unknown"}
    return status, reason


def replay(cvc5, z3):
    rows = []
    for family, size, expected in product(FAMILIES, SIZES, ("sat", "unsat")):
        source = query(family, size, expected)
        for (backend, executable), limit in product((("cvc5", cvc5), ("z3", z3)), LIMITS):
            verdict, reason = classify(backend, executable, source, limit)
            assert verdict in (expected, "unknown"), (family, size, expected, backend, limit, verdict)
            # No SMT response in this study carries an authenticated evidence basis or replayed model.
            disposition = classify_solver_answer(SolverAnswer(verdict, reason=reason), (), frozenset())
            assert retain_as_possible(disposition)
            rows.append({"family": family, "size": size, "oracle": expected, "backend": backend,
                         "work_limit": limit, "status": verdict, "reason": reason,
                         "retained_without_evidence": True, "query_sha256": sha256(source.encode()).hexdigest()})

    status, diagnostic = invoke([sys.executable, "-c", "import time; time.sleep(2)"], "", .05)
    assert (status, diagnostic) == ("unknown", "host-deadline")
    counts = Counter((row["backend"], row["status"]) for row in rows)
    return {
        "schema": "rt03-qflia-budget-controls-v1", "baseline": BASELINE,
        "python": platform.python_version(), "host_deadline_seconds": HOST_DEADLINE_SECONDS,
        "execution_tools": {
            role: {"version": subprocess.check_output([path, "--version"], text=True).splitlines()[0],
                   "sha256": sha256(Path(path).read_bytes()).hexdigest()}
            for role, path in (("cvc5", cvc5), ("z3", z3))
        },
        "source_sha256": {path.name: sha256(path.read_bytes()).hexdigest()
                          for path in (HERE / "run.py", PROTOTYPE / "rt03_feasibility_outcomes.py")},
        "rows": rows,
        "status_counts": {f"{tool}/{status}": count for (tool, status), count in counts.items()},
        "injected_host_timeout": {"status": status, "reason": diagnostic, "deadline_seconds": .05},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cvc5", required=True)
    parser.add_argument("--z3", required=True)
    args = parser.parse_args()
    print(json.dumps(replay(args.cvc5, args.z3), indent=2, sort_keys=True))
