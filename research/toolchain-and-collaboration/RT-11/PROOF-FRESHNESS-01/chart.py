#!/usr/bin/env python3
"""Render source and verifier interventions against the baseline receipt."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
labels = {
    "formatting/4.34.0": "Whitespace",
    "refactor/4.34.0": "Equivalent operand reorder",
    "changed/4.34.0": "Increment changed from one to two",
    "refuted/4.34.0": "Identity body",
    "baseline/4.36.0": "Checker version only",
}
print("| Intervention | Same typed subject | Same check request | Same source-bound receipt | Fresh check |")
print("| --- | --- | --- | --- | --- |")
for profile, label in labels.items():
    compared = ledger["comparison_to_baseline_434"][profile]
    outcome = ledger["checked_source_runs"][profile]["outcome"]
    flags = ["yes" if compared[key] else "no" for key in ("subject", "execution_key", "source_receipt")]
    print(f'| {label} | {" | ".join(flags)} | {outcome} |')
