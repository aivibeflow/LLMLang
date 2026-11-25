#!/usr/bin/env python3
"""Render accepted and rejected wire fixtures from the comparison ledger."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
names = {
    "strict": "Strict canonical bytes",
    "normalizing": "Normalize and verify canonical digest",
    "raw_only": "Verify raw digest alone",
}
print("| Admission model | Accepted | Rejected |")
print("| --- | ---: | ---: |")
for policy, counts in ledger["outcome_counts"].items():
    accepted = counts["accept"]
    print(f"| {names[policy]} | {accepted} | {sum(counts.values()) - accepted} |")
