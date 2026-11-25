#!/usr/bin/env python3
"""Render the finite membership comparison from the native ledger."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Arithmetic | Provider | Complete relation | Separate value and trace |")
print("| --- | --- | ---: | ---: |")
for row in ledger["rows"]:
    lo, hi = ledger["input_range_inclusive"]
    n = hi - lo + 1
    print(f'| {row["context"]} | {row["provider"]} | {row["member_count"]}/{n} | {row["marginal_count"]}/{n} |')
