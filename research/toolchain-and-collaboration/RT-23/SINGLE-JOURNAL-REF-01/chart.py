"""Render the ref state at each process stop from the ledger."""
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Backend and stop | Branch | Receipt | Paired inspection | Journal inspection |")
print("| --- | --- | --- | --- | --- |")
for name, row in ledger["cases"].items():
    if "after_kill" not in row or name.endswith("divergence"):
        continue
    state = row["after_kill"]
    branch = "Candidate" if state["branch"] == row["plan"]["candidate"] else "Base"
    receipt = "Present" if state["receipt"] is not None else "Absent"
    print(f'| {name} | {branch} | {receipt} | {state["paired_result"]} | {state["journal_result"]} |')
