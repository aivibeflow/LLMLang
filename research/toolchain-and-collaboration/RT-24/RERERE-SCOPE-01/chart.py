#!/usr/bin/env python3
"""Render the native conflict resolution and scoped reuse comparisons."""

import json
from pathlib import Path

labels = {
    "same_scope": "Same affected inputs",
    "disjoint_declaration": "Disjoint declaration added",
    "changed_choice": "Reviewed branch choice changed",
    "changed_revision": "Policy revision changed, same choice",
    "reversed_parents": "Ordered parent roles reversed",
}
ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
print("| Rebase case | Fresh exact target | Autostaged | Whole Git parent gate | Scoped approval reuse |")
print("|---|---:|---:|---:|---:|")
for case, label in labels.items():
    rows = [row for row in ledger["observations"] if row["case"] == case]
    columns = ("matches_fresh_target", "staged_by_rerere", "exact_git_parent_gate", "scoped_reuse_gate")
    cells = [f'{sum(row[column] for row in rows)}/{len(rows)}' for column in columns]
    print(f"| {label} | " + " | ".join(cells) + " |")
