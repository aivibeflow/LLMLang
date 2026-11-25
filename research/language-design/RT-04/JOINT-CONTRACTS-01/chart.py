#!/usr/bin/env python3
"""Render joint-contract control counts."""

import json
from pathlib import Path

counts = json.loads(Path(__file__).with_name("evidence.json").read_text())["counts"]
print("| Decision | Count |")
print("| --- | ---: |")
for field, label in (
    ("individually_feasible_pairs", "Individually feasible pairs"),
    ("jointly_feasible_pairs", "Pairs with a common provider"),
    ("individually_feasible_but_disjoint_pairs", "Individually feasible pairs without a common provider"),
    ("overlap_only_false_admission_pairs", "Pairs with false admissions under overlap-only checking"),
    ("unconditional_intersection_false_refusal_pairs", "Pairs with false refusals under raw postcondition intersection"),
    ("contracts_with_multiple_conforming_providers", "Contracts with multiple conforming providers"),
    ("contracts_allow_same_values_with_distinct_effects", "Contracts allowing same values with different effects"),
):
    print(f"| {label} | {counts[field]} |")
