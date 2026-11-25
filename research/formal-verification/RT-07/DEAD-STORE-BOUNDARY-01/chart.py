#!/usr/bin/env python3
"""Render guard coverage from the dead-store experiment ledger."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
print("| Guard | Admitted | False admissions | False refusals |")
print("| --- | ---: | ---: | ---: |")
for key, label in (
    ("final_cells", "Matching final cells"),
    ("hidden_write", "Hidden store"),
    ("exact_rule", "Exact criterion"),
):
    result = ledger["guards"][key]
    print(f"| {label} | {result['admitted']} | {result['false_admission']} | {result['false_refusal']} |")
