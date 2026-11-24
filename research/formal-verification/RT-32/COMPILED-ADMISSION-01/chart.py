"""Render admission outcomes for all compiled-proof controls."""
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Case | Signed bundle alone | Theorem and axiom checks alone | Combined decision |")
print("| --- | --- | --- | --- |")
for case, result in ledger["cases"].items():
    signed = "admit" if result["signature_bundle_admission"] else "reject"
    theorem = "admit" if result["type_axiom_admission"] else "reject"
    print(f'| {case} | {signed} | {theorem} | {result["full_admission"]} |')
