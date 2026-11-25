#!/usr/bin/env python3
"""Render counts for the native mixed-version Git histories."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
labels = {
    "single_v2": "Version 2 only with root check",
    "rounded": "Dual read through JavaScript Number",
    "exact_unbound": "Exact dual read without root check",
    "exact_bound": "Exact dual read with root check",
}
print("| Admission policy | Correct candidates | Valid histories refused | Invalid candidates | Expected refusals |")
print("|---|---:|---:|---:|---:|")
for policy, counts in ledger["metrics"].items():
    assert sum(counts.values()) == ledger["scenarios"]
    values = [str(counts[key]) for key in ("exact", "valid_refused", "wrong_published", "expected_refusal")]
    print(f"| {labels[policy]} | " + " | ".join(values) + " |")
