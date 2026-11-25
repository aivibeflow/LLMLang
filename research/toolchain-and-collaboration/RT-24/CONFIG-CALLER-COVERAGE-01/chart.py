#!/usr/bin/env python3
"""Render caller coverage and receipt replay counts from the native ledger."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
labels = {"source_only": "Caller source only", "source_and_flags": "Caller source and flags",
          "all_profile_union": "All profiles in the selected tree", "exact_profile": "Exact selected profile"}
print("| Coverage policy | Exact profiles | Missing call edges | Excess call edges |")
print("|---|---:|---:|---:|")
for policy, counts in ledger["metrics"].items():
    print(f"| {labels[policy]} | {counts['exact']} | {counts['missing_edges']} | {counts['excess_edges']} |")
print()
print("| Receipt swap | Replays | Equal edge sets | Accepted by edge-only gate | Accepted by profile gate |")
print("|---|---:|---:|---:|---:|")
labels = {"revision": "Other Git revision", "optimization": "Other optimization level"}
for case, counts in ledger["replay_controls"].items():
    print(f"| {labels[case]} | {ledger['native_profiles']} | {counts['old_edge_set_equal']} | "
          f"{counts['edge_only_accepts']} | {counts['profile_accepts']} |")
