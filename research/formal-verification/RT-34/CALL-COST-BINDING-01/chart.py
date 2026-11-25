"""Render proof-reuse decisions and evidence failures."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Cache and evidence rule | Proven | Refuted | Unknown | False proofs | Unbound proofs |")
print("| --- | ---: | ---: | ---: | ---: | ---: |")
fields = ("proven", "refuted", "unknown", "false_proofs", "unbound_proofs")
for policy, decisions in ledger["policies"].items():
    print(f"| {policy} | " + " | ".join(str(decisions[field]) for field in fields) + " |")
