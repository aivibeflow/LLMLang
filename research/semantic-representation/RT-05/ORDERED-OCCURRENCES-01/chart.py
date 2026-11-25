"""Render the comparison table from the replayable occurrence ledger."""
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Encoding | Distinct keys | Collapsed groups | Observation differences | Status differences |")
print("| --- | ---: | ---: | ---: | ---: |")
for mode in ("exact", "role-local-order", "unique-steps", "unordered-arguments"):
    data = ledger["results"][mode]
    keys, groups = data["distinct_keys"], data["collapsed_groups"]
    observations, statuses = data["disagreeing_observations"], data["different_status"]
    print(f"| {mode} | {keys} | {groups} | {observations:,} | {statuses:,} |")
