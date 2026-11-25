#!/usr/bin/env python3
"""Render composition controls and their observed counterexample counts."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
print("| Control | Profiles | Disagreed |")
print("| --- | ---: | ---: |")
counts = ledger["counts"]
print(f"| Existential handoff | {counts['admission_profiles']} | {counts['exists_false_admission']} |")
for label, key in (
    ("Use initial state at handler entry", "rollback_state"),
    ("Treat cancellation as retry", "cancel_is_retry"),
    ("Erase the primary trace prefix", "erase_prefix"),
):
    print(f"| {label} | {counts['composition_profiles']} | {ledger['disagreements'][key]} |")
