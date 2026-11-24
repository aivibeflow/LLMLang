#!/usr/bin/env python3
"""Cross-check bounded atomic RMW and fence outcomes with two SMT solvers."""

import argparse
from dataclasses import replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess

from cases import cases
from enumerate_model import allowed_witnesses
from smt_model import smt


HERE = Path(__file__).resolve().parent
SOLVERS = {
    "z3": ("-in",),
    "cvc5": ("--lang=smt2", "--incremental"),
}


def execute(command, source=None):
    run = subprocess.run(command, input=source, text=True, capture_output=True, timeout=90)
    if run.returncode or run.stderr:
        raise ValueError(f"Tool failed {command}: {run.returncode}, {run.stderr!r}")
    return run.stdout


def possible_values(threads):
    by_location = {}
    operations = [op for thread in threads for op in thread]
    for location in sorted({op.location for op in operations if op.location}):
        writes = [op for op in operations if op.location == location and op.writes]
        values = {0, *(op.value for op in writes if not op.reads)}
        for op in writes:
            if op.reads:
                values |= {(prior + op.value) & 255 for prior in values}
        by_location[location] = sorted(values)
    return {op.name: by_location[op.location] for op in operations if op.reads}


def exhaustive_rows(case, solver_commands):
    domains = possible_values(case.threads)
    inputs = list(product(*domains.values()))
    accepted = set()
    globally_ordered = set()
    for witness in allowed_witnesses(replace(case, outcome={})):
        observed = tuple(witness["observed"][reader] for reader in domains)
        accepted.add(observed)
        if witness["global_order"]:
            globally_ordered.add(observed)
    if not accepted.issubset(inputs):
        raise ValueError(f"An enumerated outcome exceeds its finite domain for {case.name}")

    formulas = {}
    for name, strict, expected in (("axiomatic", False, accepted), ("global", True, globally_ordered)):
        unspecialized = smt(replace(case, outcome={}), globally_ordered=strict).removesuffix("(check-sat)\n")
        queries = []
        for outcome in inputs:
            equalities = [f"(assert (= observed_{reader} {value}))"
                          for reader, value in zip(domains, outcome, strict=True)]
            queries.extend(["(push 1)", *equalities, "(check-sat)", "(pop 1)"])
        bundle = unspecialized + "\n".join(queries) + "\n"
        formulas[name] = sha256(bundle.encode("ascii")).hexdigest()
        agreed = ["sat" if outcome in expected else "unsat" for outcome in inputs]
        for solver, command in solver_commands.items():
            actual = execute(command, bundle).splitlines()
            if actual != agreed:
                raise ValueError(f"{solver} disagreed on {case.name} ({name}): {actual}")
    return {"domains": domains, "queries_per_model": len(inputs), "accepted_outcomes": sorted(accepted),
            "global_order_outcomes": sorted(globally_ordered), "formula_sha256": formulas}


def replay(args):
    commands = {name: (getattr(args, name), *options) for name, options in SOLVERS.items()}
    tested = []
    by_graph = {}
    for case in cases():
        graph = (case.threads, case.adjacent_rmw)
        if graph not in by_graph:
            by_graph[graph] = (case.name, exhaustive_rows(case, commands))
        layout, graph_result = by_graph[graph]
        witnesses = list(allowed_witnesses(case))
        observed = tuple(case.outcome[reader] for reader in graph_result["domains"])
        if (bool(witnesses) != case.allowed
                or (observed in graph_result["accepted_outcomes"]) != case.allowed):
            raise ValueError(f"Unexpected bounded outcome for {case.name}")
        ordered = observed in graph_result["global_order_outcomes"]
        if (case.sequential is not None and ordered != case.sequential
                or ordered != any(w["global_order"] for w in witnesses)):
            raise ValueError(f"Unexpected global-order witness result for {case.name}")
        tested.append({"name": case.name, "graph": layout, "outcome": case.outcome,
                       "allowed": case.allowed, "global_order": ordered, "witnesses": witnesses})

    return {
        "schema": "llmlang-bounded-atomic-rmw-fences-v1",
        "tools": {name: execute((getattr(args, name), "--version")).splitlines()[0] for name in SOLVERS},
        "input_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                         for name in ("cases.py", "enumerate_model.py", "smt_model.py", "run.py")},
        "graphs": dict(by_graph.values()),
        "tested": tested,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in SOLVERS:
        parser.add_argument(f"--{name}", default=name)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(replay(args), indent=2) + "\n", encoding="utf-8")
