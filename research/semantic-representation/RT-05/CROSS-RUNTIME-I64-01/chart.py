#!/usr/bin/env python3
"""Render the native decoder and semantic identity comparison."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
labels = {
    "number": "Default JavaScript Number",
    "safe_number": "Safe-integer subset",
    "lexeme": "Exact numeric source lexeme",
    "text": "Canonical decimal text",
    "hex": "Fixed-width hexadecimal",
}
print("| Decoder | Accepted values | Wrong values | Distinct pairs merged | Noncanonical or invalid controls accepted | Wire bytes |")
print("|---|---:|---:|---:|---:|---:|")
for policy, values in ledger["metrics"].items():
    print(f'| {labels[policy]} | {values["accepted"]}/{ledger["distinct_values"]} | '
          f'{values["wrong_values"]} | {values["merged_distinct_pairs"]} | {values["accepted_controls"]} | '
          f'{values["wire_bytes"]:,} |')
