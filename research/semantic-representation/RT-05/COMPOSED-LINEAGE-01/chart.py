"""Render the selection-review decisions counted against the declared oracle."""
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Policy | Excess successor grants | Missing eligible grants | Unknown histories |")
print("| --- | ---: | ---: | ---: |")
for policy, counts in ledger["summary"].items():
    print(f'| {policy} | {counts["excess"]} | {counts["omitted"]} | {counts["unknown"]} |')
