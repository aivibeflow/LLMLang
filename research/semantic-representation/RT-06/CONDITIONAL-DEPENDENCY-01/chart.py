"""Render observed misses and extras from the closure comparison ledger."""
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Method | Queries with misses | Missed targets | Queries with extras | Extra targets |")
print("| --- | ---: | ---: | ---: | ---: |")
for name, row in ledger["rows"].items():
    misses, missed = row["queries_with_misses"], row["missed_targets"]
    extras, added = row["queries_with_extras"], row["extra_targets"]
    print(f"| {name} | {misses:,} | {missed:,} | {extras:,} | {added:,} |")
