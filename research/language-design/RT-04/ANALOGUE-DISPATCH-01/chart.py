#!/usr/bin/env python3
"""Render finite ranking and dispatch comparison counts."""

import json
from pathlib import Path

counts = json.loads(Path(__file__).with_name("evidence.json").read_text())["counts"]
print("| Comparison | Count |")
print("| --- | ---: |")
for key, label in (
    ("scored_candidates", "Scored candidate occurrences"),
    ("catalogs", "Sampled catalogs"),
    ("catalogs_with_refining_candidate", "Catalogs with a refining candidate"),
    ("unsafe_top_one", "Top-ranked contract fails refinement"),
    ("unsafe_top_one_with_refining_alternative", "Top-ranked contract fails despite a refining alternative"),
    ("refining_candidate_outside_top_three", "All refining candidates outside top three"),
    ("unfiltered_analogue_violates_required_contract", "Unfiltered proposals violate the required contract"),
    ("unfiltered_analogue_changes_exact_provider", "Unfiltered proposals change the exact provider"),
):
    print(f"| {label} | {counts[key]} |")
