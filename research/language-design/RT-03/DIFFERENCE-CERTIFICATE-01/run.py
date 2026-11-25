"""Execute the exact difference-query proof and certificate admission controls."""

import argparse
from dataclasses import replace
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

from checker import Certificate, Edge, Query, classify


def solver(cvc5, query):
    return subprocess.run([cvc5, "--lang=smt2"], input=query.formula(), capture_output=True,
                          check=True, text=True, timeout=15).stdout.strip()


def execute(cvc5, lean):
    model_version = subprocess.check_output([lean, "--version"], text=True).strip()
    assert "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9" in model_version
    model = subprocess.check_output([lean, "-DwarningAsError=true", HERE / "Certificate.lean"], text=True).splitlines()
    assert len(model) == 2 and all("sorryAx" not in row for row in model)
    matrix = []
    for left, right in product(range(-2, 3), repeat=2):
        query = Query("two-leg-route-v1", "integer-difference-v1", 2,
                      (Edge(0, 1, left, "enter-v1"), Edge(1, 0, right, "leave-v1")))
        cert = Certificate(query.identity, (0, 1))
        status = solver(cvc5, query)
        assert status == ("unsat" if left + right < 0 else "sat")
        before, after = classify(query, status), classify(query, status, cert)
        assert before == ("unknown", True)
        assert after == (("infeasible", False) if left + right < 0 else before)
        matrix.append({"bounds": [left, right], "solver": status, "query": query.identity,
                       "formula_sha256": sha256(query.formula().encode()).hexdigest(),
                       "raw_policy": before, "checked_policy": after})

    base = Query("route-v1", "integer-difference-v1", 3,
                 (Edge(0, 1, -1, "a-v1"), Edge(1, 2, -1, "b-v1"), Edge(2, 0, 1, "c-v1")))
    proof = Certificate(base.identity, (0, 1, 2))
    assert solver(cvc5, base) == "unsat"
    assert classify(base, "unsat", proof) == ("infeasible", False)
    revised_route = replace(base, route_revision="route-v2")
    revised_premise = replace(base, constraints=(replace(base.constraints[0], premise_revision="a-v2"), *base.constraints[1:]))
    feasible = replace(base, constraints=(*base.constraints[:2], Edge(2, 0, 2, "c-v2")))
    assert revised_route.formula() == revised_premise.formula() == base.formula()
    assert solver(cvc5, feasible) == "sat"
    foreign_profile = replace(base, profile="wrapping-32-bit")
    controls = []
    for label, query, status, certificate in (
        ("foreign route with identical formula", revised_route, "unsat", proof),
        ("different premise revision with identical formula", revised_premise, "unsat", proof),
        ("changed bound with refreshed subject", feasible, "unsat", Certificate(feasible.identity, proof.edges)),
        ("missing edge", base, "unsat", replace(proof, edges=(0, 1))),
        ("noncontiguous selection", base, "unsat", replace(proof, edges=(0, 2, 1))),
        ("out-of-range edge index", base, "unsat", replace(proof, edges=(0, 1, 7))),
        ("non-integer interpretation", foreign_profile, "unsat", Certificate(foreign_profile.identity, proof.edges)),
        ("host could not produce a completed status", base, "unknown", proof),
    ):
        outcome = classify(query, status, certificate)
        assert outcome == ("unknown", True)
        controls.append({"case": label, "query": query.identity, "claimed_status": status, "result": outcome})

    files = [HERE / "Certificate.lean", HERE / "checker.py", HERE / "run.py",
             PROTOTYPE / "rt03_feasibility_outcomes.py"]
    return {
        "schema": "rt03-exact-difference-certificate-v1",
        "python": platform.python_version(),
        "cvc5": subprocess.check_output([cvc5, "--version"], text=True).splitlines()[0],
        "lean": model_version, "axioms": model,
        "source_sha256": {path.name: sha256(path.read_bytes()).hexdigest() for path in files},
        "matrix": matrix, "controls": controls,
        "checked_three_edge_walk": {"query": base.identity, "edges": proof.edges, "policy": ["infeasible", False]},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True)
    parser.add_argument("--cvc5", required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.cvc5, args.lean), indent=2, sort_keys=True))
