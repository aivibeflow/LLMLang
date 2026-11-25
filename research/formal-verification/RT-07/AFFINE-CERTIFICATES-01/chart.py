"""Render scoped proof routing and branch evidence from the kernel replay."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Query | cvc5 status | Branches with a certificate | Restricted result |")
print("| --- | --- | ---: | --- |")
for name, query in ledger["queries"].items():
    branches = query["branches"]
    covered = sum(branch["weights"] is not None for branch in branches)
    result = "Checked refutation" if query["affine"] == "checked_refutation" else "UNKNOWN"
    print(f"| {name} | {query['cvc5']} | {covered}/{len(branches)} | {result} |")
