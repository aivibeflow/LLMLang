#!/usr/bin/env python3
"""Render shared-identity and observation counts for both teardown routes."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
labels = {"native": "Native implicit teardown", "explicit": "Explicit ordered teardown"}
print("| Route | Shared exact graphs | Early-exit disagreements | Completed disagreements |")
print("|---|---:|---:|---:|")
for mode, result in ledger["metrics"].items():
    count = ledger["source_cases_per_profile"] // len(labels)
    print(f'| {labels[mode]} | {result["identical_hash_pairs"]}/{count} | '
          f'{result["abort_differences"]}/{count * 28} | {result["completed_differences"]}/{count * 4} |')
