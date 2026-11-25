"""Render external receipt recovery counts from the native replay."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Recovery policy | Receipt rows | False receipts | Eligible outcomes unresolved |")
print("| --- | ---: | ---: | ---: |")
for policy, counts in ledger["counts"].items():
    fields = ("receipts", "false_receipts", "eligible_unresolved")
    print(f"| {policy} | " + " | ".join(str(counts[field]) for field in fields) + " |")
