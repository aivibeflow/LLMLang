"""Render the published effect and stale-authority outcome counts."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Policy | Effects committed | False admissions | False refusals | WAL snapshot conflicts |")
print("| --- | ---: | ---: | ---: | ---: |")
fields = ("committed", "false_admission", "false_refusal", "busy_snapshot")
for policy, values in ledger["counts"].items():
    print(f"| {policy} | " + " | ".join(str(values[field]) for field in fields) + " |")
