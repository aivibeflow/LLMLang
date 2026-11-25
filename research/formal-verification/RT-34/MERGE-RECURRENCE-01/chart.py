"""Render proof-bound precision for the measured input families."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Input family | Sizes | Comparison bound attained | Comparison bound loose | Equal-floor writes undercount |")
print("| --- | ---: | ---: | ---: | ---: |")
fields = ("cases", "exact_comparison_bound", "loose_comparison_bound", "equal_halves_undercounts")
for family, result in ledger["profiles"].items():
    print(f"| {family} | " + " | ".join(str(result[field]) for field in fields) + " |")
