#!/usr/bin/env python3
"""Render native binding/capture mismatches for each projection."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
labels = {
    "source_token": "Physical source token",
    "decoded": "Decoded spelling",
    "nfc": "NFC name",
    "nfkc": "NFKC name",
    "nfkc_all_text": "NFKC name and literal data",
    "same_cell": "Native name rule with one cell for equal names",
    "native_profile": "Profile-specific assignment and capture",
}
print("| Projection | CPython | Node | Rust O0 | Rust O3 |")
print("|---|---:|---:|---:|---:|")
profiles = ledger["profile_mismatches"]
for mode, label in labels.items():
    mismatches = " | ".join(str(values[mode]) for values in profiles.values())
    print(f"| {label} | {mismatches} |")
