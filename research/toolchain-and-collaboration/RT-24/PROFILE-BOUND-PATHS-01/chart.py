#!/usr/bin/env python3
"""Render name-profile decisions over native clean Git candidates."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
labels = {
    "physical": "Exact Git paths and Linux checkout",
    "ascii_paths": "ASCII case-insensitive complete paths",
    "unicode_paths": "Unicode profile on complete paths",
    "unicode_prefixes": "Unicode profile on files and directory prefixes",
}
keys = ("accepted_valid", "wrongly_accepted", "correctly_refused", "refused_valid")
print("| Admission policy | Valid candidates admitted | Profile collisions missed | Profile collisions refused | Valid candidates refused |")
print("|---|---:|---:|---:|---:|")
for policy, counts in ledger["metrics"].items():
    assert sum(counts.values()) == ledger["native_clean"]
    print(f"| {labels[policy]} | " + " | ".join(str(counts[key]) for key in keys) + " |")
