#!/usr/bin/env python3
"""Render exact-ref publication decisions for the configured merge cases."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
labels = {"parents": "Clean Git and approved parents", "provider_only": "Reuse by provider name",
          "whole_tree": "Reuse by exact Git tree", "bound_scope": "Reuse by exact build and grant scope",
          "fresh": "Fresh exact candidate check"}
keys = ("exact_publications", "invalid_publications", "valid_refusals", "expected_refusals")
print("| Publication policy | Correct publications | Invalid publications | Valid candidates refused | Expected refusals |")
print("|---|---:|---:|---:|---:|")
for policy, counts in ledger["metrics"].items():
    assert sum(counts.values()) == ledger["histories"]
    print(f"| {labels[policy]} | " + " | ".join(str(counts[k]) for k in keys) + " |")
