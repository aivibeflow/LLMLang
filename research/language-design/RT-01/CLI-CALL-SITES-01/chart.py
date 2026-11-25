#!/usr/bin/env python3
"""Render source closure and behavioral outcomes across caller binding policies."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
labels = {
    "filesystem_path": "Original path",
    "current_alias": "Current public alias",
    "keep_previous_pin": "Retain the old exact provider",
    "exact_calls": "Exact call-site plan and selected source",
    "warm_exact_calls": "Exact plan resolved from warm store",
}
print("| Binding policy | Behavior-only passes | Eligible candidates | Missing selections | Outside current tree | Wrong case vectors |")
print("|---|---:|---:|---:|---:|---:|")
for policy, values in ledger["metrics"].items():
    total = ledger["git_candidates"]
    print(f'| {labels[policy]} | {values["native_only_claims"]}/{total} | {values["eligible"]}/{total} | '
          f'{values["missing_choices"]} | {values["outside_inventory"]} | {values["disagreements"]} |')
