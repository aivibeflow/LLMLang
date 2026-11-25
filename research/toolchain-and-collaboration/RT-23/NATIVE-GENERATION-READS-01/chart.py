"""Render the observed multi-file outcomes at each controlled interleaving."""
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Reader and writer transition | Writer result while reader waits | Read result |")
print("| --- | --- | --- |")
for label, case in ledger["cases"].items():
    print(f'| {label} | {case["transition"]} | {case["observation"]["status"]} |')
