#!/usr/bin/env python3
"""Render artifact and reuse counts for the scoped conformance receipts."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
print("| Decision | Count |")
print("| --- | ---: |")
for key, label in (
    ("observations", "Executed observations"),
    ("checked_scopes", "Scopes matching the full observation reference"),
    ("refuted_scopes", "Scopes with an observed mismatch"),
    ("ordered_receipt_reuse_pairs", "Receipt and request combinations"),
    ("exact_reuse_admissions", "Exact receipt reuses"),
    ("same_observations_different_scope", "Matching observation digests with a different scope"),
):
    print(f"| {label} | {ledger[key]} |")
