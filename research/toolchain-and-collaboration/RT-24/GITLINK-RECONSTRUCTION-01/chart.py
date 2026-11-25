#!/usr/bin/env python3
"""Render exact and incorrect submodule reconstruction decisions."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
labels = {"worktree": "Read the nested working file", "nested_head": "Read the nested HEAD",
          "upstream_tip": "Read the configured origin tip", "exact_gitlink": "Validate manifest, gitlink and exact origin"}
keys = ("exact", "wrong_acceptance", "available_refused", "expected_refusal")
print("| Reconstruction policy | Exact | Wrong acceptances | Available dependencies refused | Expected refusals |")
print("|---|---:|---:|---:|---:|")
for policy, counts in ledger["metrics"].items():
    assert sum(counts.values()) == ledger["scenarios"]
    print(f"| {labels[policy]} | " + " | ".join(str(counts[k]) for k in keys) + " |")
