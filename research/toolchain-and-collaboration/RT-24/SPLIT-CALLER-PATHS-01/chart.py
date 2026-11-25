"""Render the exact-tree gate comparison from the replayable ledger."""
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Case | Closed source and exact CIP gate | With source route check | Route findings |")
print("| --- | --- | --- | ---: |")
for name, case in ledger["cases"].items():
    findings = len(case["path_errors"])
    print(f'| {name} | {case["existing_gate"]} | {case["path_bound_gate"]} | {findings} |')
