#!/usr/bin/env python3
"""Render the proof status comparison against individual arrival schedules."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
print("| Comparison | Count |")
print("| --- | ---: |")
for key, label in (
    ("subset_premise_pairs", "Receipt subsets and premise states"),
    ("ordered_profiles", "Arrival orders and premise states"),
    ("last_arrival_differs", "Latest verdict disagrees with full history"),
    ("closed_proof_demoted_to_unresolved", "Latest verdict hides a closed proof"),
    ("order_sensitive_last_arrival_pairs", "Subset/premise pairs sensitive to arrival order"),
):
    print(f"| {label} | {ledger['counts'][key]} |")
