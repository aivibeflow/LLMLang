#!/usr/bin/env python3
"""Render unsafe-tail outcomes for the pinned solver processes."""

import json
from pathlib import Path

evidence = json.loads(Path(__file__).with_name("evidence.json").read_text())
print("| Solver | Faults withheld | Silent profile violations | Blind tail answers | Disagree with approved fresh replay | Recoverable |")
print("| --- | ---: | ---: | ---: | ---: | ---: |")
for solver, row in evidence["solvers"].items():
    counts = row["counts"]
    columns = " | ".join(str(counts[key]) for key in (
        "quarantined", "faults_without_solver_diagnostic", "blind_answers_after_fault",
        "wrong_blind_answers_against_approved_repair", "fresh_repaired_contexts",
    ))
    print(f"| {solver} | {columns} |")
