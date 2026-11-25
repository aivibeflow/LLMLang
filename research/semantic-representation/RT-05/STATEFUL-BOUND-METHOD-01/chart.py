#!/usr/bin/env python3
"""Render observed differences between three bound-method descriptors."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
labels = {"code_only": "Method code and type", "values_only": "Receiver values with separate state",
          "exact": "Bound method and shared cell table"}
keys = ("changed_recipe_vectors", "colliding_context_pairs", "colliding_pairs_with_different_traces")
print("| Descriptor | Recipe vectors changed | Distinct contexts sharing a key | Colliding pairs with different traces |")
print("|---|---:|---:|---:|")
for policy, counts in ledger["metrics"].items():
    print(f"| {labels[policy]} | " + " | ".join(f"{counts[key]:,}" for key in keys) + " |")
