#!/usr/bin/env python3
"""Render exact Git batch custody evidence and policy counterexamples."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
keys = ("path_presence", "exact_dedicated", "exact_and_register_links", "all_pr_blobs")
labels = {"published_tree": "Published main", "deleted_dedicated_ledger": "Remove one ledger path",
          "substituted_ledger_bytes": "Replace a ledger at the same path",
          "omitted_registry_link": "Remove one exact registry edge",
          "retargeted_registry_link": "Retarget an edge to an existing path"}
counts = (("Pull requests", "pull_requests"), ("PR path touches", "path_touches"),
          ("Distinct published paths", "distinct_paths"), ("Exact dedicated files", "dedicated_paths"),
          ("Shared registries", "shared_registries"),
          ("Registry blobs rewritten between PR head and integration step", "whole_registry_blob_changes_across_squashes"),
          ("Exact registry edges to the corresponding PR evidence", "expected_exact_registry_links"))
print("| Published evidence | Count |")
print("|---|---:|")
for label, field in counts:
    print(f"| {label} | {ledger[field]} |")
print()
print("| Case | Presence | Exact dedicated files | Exact files and registry edges | Every PR blob unchanged |")
print("|---|---|---|---|---|")
for name, checks in ledger["controls"]["outcomes"].items():
    print(f"| {labels[name]} | " + " | ".join("Admit" if checks[key] else "Refuse" for key in keys) + " |")
