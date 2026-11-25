#!/usr/bin/env python3
"""Render the checked mutable graph proof and archive projection counts."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
model = ledger["model_theorem_axioms"]
archive = len(ledger["archive_equalities"])
assert "splitting_changes_trace" in model
counts = (
    ("General model theorems", len(model) - 1),
    ("Checked projection counterexamples", 1),
    ("Exact native class equations", archive),
    ("Archived recipe vectors compared", archive * ledger["archived_recipes"] * len(ledger["archive_paths"])),
    ("Refused false proofs", int(ledger["incorrect_split_preservation_proof"] == "rejected")),
)
print("| Checked result | Count |")
print("|---|---:|")
for label, count in counts:
    print(f"| {label} | {count:,} |")
