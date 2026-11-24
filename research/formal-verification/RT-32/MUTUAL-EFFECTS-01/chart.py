"""Render observation and finite-contract coverage from the evidence ledger."""
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Group encoding | SPG and Lean observations | In finite trace contract | Outside finite contract |")
print("| --- | ---: | ---: | ---: |")
for policy, row in ledger["encodings"].items():
    outside = row["out_of_finite_contract"]
    print(f'| {policy} | {row["observations"]} | {row["observations"] - outside} | {outside} |')
