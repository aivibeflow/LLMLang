#!/usr/bin/env python3
"""Render the native merge and exact export comparison."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
labels = {
    "symbol_alias": "Unchanged operation and renamed symbol",
    "abi_receipt_missing": "New ABI with no selected provider receipt",
    "abi_crossed_receipt": "New ABI with exact crossed receipt",
    "abi_incompatible": "Selected provider lacks ABI support",
    "scope_receipt_missing": "Wider scope with no selected provider receipt",
    "scope_incompatible": "Selected behavior fails wider scope",
    "wrong_receipt_bytes": "Exact claim key with stale check bytes",
    "dormant_binding_removed": "Export activated and its binding deleted",
    "catalog_alias": "Public name alias resolves to same operation",
}
print("| Merge case | Contract-only accepts | Exact gate publishes | Disposition |")
print("|---|---:|---:|---|")
for name, label in labels.items():
    rows = [row["checked"] for row in ledger["cases"] if row["case"] == name]
    count = len(rows)
    loose = sum(row["contract_only_gate"] for row in rows)
    exact = sum(row["exact_gate"] for row in rows)
    disposition, = {row["status"] for row in rows}
    print(f"| {label} | {loose}/{count} | {exact}/{count} | {disposition.replace('_', ' ')} |")
