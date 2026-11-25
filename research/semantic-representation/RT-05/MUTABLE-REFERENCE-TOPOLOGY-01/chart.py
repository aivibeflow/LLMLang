#!/usr/bin/env python3
"""Render the mutable reference graph comparison table."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
labels = {"physical_ids": "Physical identifiers", "root_local": "Separate graph per root", "shared_graph": "One shared graph"}
keys = ("trace_drift", "changed_key", "false_identity_pairs", "false_identity_observation_pairs")
print("| Graph representation | Changed recipe traces | Changed keys under relabeling | Distinct graph pairs sharing a key | Colliding pairs with different traces |")
print("|---|---:|---:|---:|---:|")
for policy, counts in ledger["metrics"].items():
    print(f"| {labels[policy]} | " + " | ".join(f"{counts[name]:,}" for name in keys) + " |")
