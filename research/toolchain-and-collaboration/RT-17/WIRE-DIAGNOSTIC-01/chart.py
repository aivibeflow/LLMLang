"""Render the exact number of incorrect or unnecessary diagnostic deliveries."""
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Freshness scope | Wrong delayed pushes | Wrong conditional pulls | Unnecessary invalidations |")
print("| --- | ---: | ---: | ---: |")
for scope, totals in ledger["totals"].items():
    print(f'| {scope} | {totals["wrongPush"]} | {totals["wrongPull"]} | {totals["unnecessaryInvalidation"]} |')
