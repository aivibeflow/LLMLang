"""Render the tested policy decisions from the Git merge evidence."""
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Policy | Excess grants | Missed grants | Unknown |")
print("| --- | ---: | ---: | ---: |")
for name, counts in ledger["summaries"].items():
    print(f'| {name} | {counts["excess_grants"]} | {counts["missed_grants"]} | {counts["unknown"]} |')
