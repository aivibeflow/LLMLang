"""Render native effect, blocking and recovery observations."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Policy | File replaced | Stale effects | Unrelated revoke postponed | Effect without receipt |")
print("| --- | ---: | ---: | ---: | ---: |")
for policy, counts in ledger["counts"].items():
    fields = ("replaced", "stale_effects", "unrelated_revocation_postponed", "effect_without_receipt")
    print(f"| {policy} | " + " | ".join(str(counts[field]) for field in fields) + " |")
