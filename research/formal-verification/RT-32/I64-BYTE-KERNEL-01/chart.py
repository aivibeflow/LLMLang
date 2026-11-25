#!/usr/bin/env python3
"""Render the verification counts recorded by the signed codec ledger."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
examples = {"uncheckedUpperAliasesLower", "networkByteOrderMatters"}
model = ledger["model_theorem_axioms"]
assert examples <= set(model)
print("| Checked result | Count |")
print("|---|---:|")
print(f"| General model theorems | {len(model) - len(examples)} |")
print(f"| Policy counterexamples | {len(examples)} |")
print(f"| Exact native archive equalities | {len(ledger['archive_equalities'])} |")
print(f"| Refused false proofs | {int(ledger['incorrect_wraparound_proof'] == 'rejected')} |")
