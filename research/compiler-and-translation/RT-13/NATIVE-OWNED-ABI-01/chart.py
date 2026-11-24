"""Render outcomes from the ABI ledger and require both profiles to agree."""
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Caller and transfer rule | Rows per optimization profile | Different physical-state pairs | Second starts per physical mode |")
print("| --- | ---: | ---: | ---: |")
for name, row in ledger["runs"].items():
    if name.endswith("/O0"):
        assert ledger["runs"][name[:-1] + "3"] == row
        print(f'| {name[:-3]} | {row["rows"]:,} | {row["physical_split_pairs"]:,} | {row["second_starts_per_physical_mode"]:,} |')
