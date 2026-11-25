#!/usr/bin/env python3
"""Render canonicalization comparisons from the native observation ledger."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
labels = {
    "surface_order": "Full surface order",
    "ordered_effects": "Ordered observable operands",
    "field_map": "Field map only",
}
print("| Projection | Exact classes | Equivalent pairs sharing a hash | Distinct pairs sharing a hash | Observation mismatches |")
print("|---|---:|---:|---:|---:|")
for key, data in ledger["policies"].items():
    print(f'| {labels[key]} | {data["classes"]} | {data["same_behavior_pairs"]} | '
          f'{data["distinct_behavior_pairs"]} | {data["observation_mismatches"]} |')
