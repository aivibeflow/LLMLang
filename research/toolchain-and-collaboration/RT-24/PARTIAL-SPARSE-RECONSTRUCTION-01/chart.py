#!/usr/bin/env python3
"""Render the native partial and sparse reconstruction outcomes."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
labels = {"worktree": "Visible working files", "path_cache": "Working files with path cache",
          "pinned_git": "Pinned tree and local Git blobs", "pinned_git_cache": "Pinned tree and verified blob cache"}
keys = ("exact", "wrong_acceptance", "available_refused", "refused")
print("| Reconstruction policy | Exact | Wrong acceptances | Available snapshots refused | Expected refusals |")
print("|---|---:|---:|---:|---:|")
for policy, counts in ledger["metrics"].items():
    assert sum(counts.values()) == ledger["scenarios"]
    print(f"| {labels[policy]} | " + " | ".join(str(counts[key]) for key in keys) + " |")
