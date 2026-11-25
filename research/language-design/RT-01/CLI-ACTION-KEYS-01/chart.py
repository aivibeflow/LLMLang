#!/usr/bin/env python3
"""Render build-action reuse and native output differences by key design."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
names = {
    "entry_only": "Entry hash",
    "snapshot_only": "Semantic snapshot",
    "whole_inputs": "Whole snapshot and all action inputs",
    "scoped_inputs": "Exact scoped action inputs",
}
print("| Key design | Planned compilations | Stale actions | Output differences | Masked invalid provider |")
print("|---|---:|---:|---:|---:|")
for name, row in ledger["metrics"].items():
    print(f'| {names[name]} | {row["compiled"]} | {row["stale_action"]} | '
          f'{row["output_case_differences"]} | {row["masked_contract_failures"]} |')
