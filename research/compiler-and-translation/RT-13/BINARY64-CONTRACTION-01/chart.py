"""Render native binary64 comparison counts from the replayable ledger."""
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Profile | Triples | Expression differences from separate rounding | Explicit FMA differences from fused rounding |")
print("| --- | ---: | ---: | ---: |")
for profile, row in ledger["results"].items():
    rows = row["rows"]
    split = row["plain_mismatches_to_separate_rounding"]
    fused = row["explicit_mismatches_to_fused_rounding"]
    print(f"| {profile} | {rows:,} | {split:,} | {fused:,} |")
