"""Render the normalized policy comparison from the checked ledger."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Release evidence | False admissions | False refusals |")
print("| --- | ---: | ---: |")
for policy, row in ledger["policy_mismatches_per_profile"].items():
    print(f"| {policy} | {row['unsafe']} | {row['unnecessary_refusal']} |")
