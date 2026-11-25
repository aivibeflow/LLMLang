#!/usr/bin/env python3
"""Render the protocol and maintenance cost tables from the native ledger."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
labels = {
    "pinned_only": "Pinned only",
    "current_root": "Current root",
    "fresh_rows": "Fresh rows",
    "complete_key": "Complete key",
}
print("| Gate | Exact | Refused | Ineligible | Stale or incomplete |")
print("|---|---:|---:|---:|---:|")
for gate, counts in ledger["protocol_aggregate"].items():
    cells = [str(counts.get(verdict, 0)) for verdict in ("exact", "refused", "ineligible", "stale_or_incomplete")]
    print(f"| {labels[gate]} | " + " | ".join(cells) + " |")

print()
print("| Change | Update | Deletes | Writes | Write payload bytes | Rows read for compare/validation | Allocated database bytes |")
print("|---|---|---:|---:|---:|---:|---:|")
for row in ledger["maintenance"]:
    if row["size"] != 1024:
        continue
    print(f'| {row["change"]} | {row["strategy"]} | {row["rows_removed"]} | {row["rows_written"]} | '
          f'{row["logical_write_bytes"]} | {row["comparison_rows"] + row["validation_rows"]} | '
          f'{row["database_allocated_bytes"]} |')
