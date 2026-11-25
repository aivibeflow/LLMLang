#!/usr/bin/env python3
"""Render failures by construction phase from the native comparison ledger."""

import json
from pathlib import Path

labels = {
    "separate_orders": "Separate acquisition, abort and completed orders",
    "canonical_fields": "Canonical field order throughout",
    "init_for_both": "Initializer order for acquisition and completed drop",
    "schema_for_both": "Schema order for acquisition and completed drop",
    "reverse_all": "Reverse acquisition for all drop",
    "forward_abort": "Forward acquisition prefix on abort",
    "schema_abort": "Filtered schema order on abort",
}
ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
print("| Projection | Exact classes | Early-exit mismatches | Completed mismatches |")
print("|---|---:|---:|---:|")
for policy, result in ledger["metrics"].items():
    print(f'| {labels[policy]} | {result["classes"]} | {result["abort_mismatch"]} | {result["completed_mismatch"]} |')
