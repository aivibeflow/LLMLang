#!/usr/bin/env python3
"""Render the contract adequacy decision counts."""

import json
from pathlib import Path

counts = json.loads(Path(__file__).with_name("evidence.json").read_text())["counts"]
print("| Decision | Count |")
print("| --- | ---: |")
for key, label in (
    ("feasible_candidate_pairs", "Pairs with a feasible candidate"),
    ("feasible_inadequate_pairs", "Feasible pairs that fail transfer"),
    ("inadequate_despite_coverage", "Failed transfer despite eligibility coverage"),
    ("adequate_without_admission_coverage", "Functional transfer without eligibility coverage"),
    ("infeasible_vacuous_implication_pairs", "Pairs with infeasible candidate and vacuous implication"),
    ("infeasible_breaks_pointwise_equivalence", "Infeasible pairs where pointwise inclusion fails"),
):
    print(f"| {label} | {counts[key]} |")
