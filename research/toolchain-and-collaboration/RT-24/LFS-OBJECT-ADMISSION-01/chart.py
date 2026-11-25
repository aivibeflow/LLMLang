#!/usr/bin/env python3
"""Render Git LFS representation and admission outcomes."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
labels = {"git_blob": "Read only the Git blob", "worktree": "Read working bytes",
          "worktree_path_cache": "Read working bytes or cache by path", "exact": "Verify manifest, pointer and object bytes"}
keys = ("exact", "wrong_acceptance", "available_refused", "expected_refusal")
print("| Reconstruction policy | Exact | Wrong acceptances | Available snapshots refused | Expected refusals |")
print("|---|---:|---:|---:|---:|")
for policy, counts in ledger["metrics"].items():
    assert sum(counts.values()) == ledger["scenarios"]
    print(f"| {labels[policy]} | " + " | ".join(str(counts[k]) for k in keys) + " |")
