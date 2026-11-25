#!/usr/bin/env python3
"""Render each cross-backend rebase case from its measured ledger."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
labels = {
    "ordinary_destination": "Ordinary destination edit",
    "restored_terminal": "Later commit restores the old call",
    "disjoint_semantic_destination": "Disjoint destination declaration",
    "exact_destination": "Destination already has intended call",
    "competing_destination": "Destination has another exact call",
    "no_residual_disjoint": "No merge-only change, disjoint declaration",
    "mixed_unrecognized_residual": "Caller and ordinary merge-only changes",
}
decisions = {
    "reapply": "Reapply checked caller change",
    "already_applied": "Accept exact caller",
    "precondition_conflict": "Refuse changed caller baseline",
    "no_residual": "Accept automatic merge",
    "unsupported_residual": "Refuse unsupported paths",
}
print("| Source and destination case | Closed rebase | Old terminal root equal | Checked disposition |")
print("|---|---:|---:|---|")
for key, label in labels.items():
    rows = [row for row in ledger["observations"] if row["case"] == key]
    closed = sum(row["closure_gate"] for row in rows)
    terminal = sum(row["terminal_root_gate"] for row in rows)
    verdicts = {row["residual_gate"] for row in rows}
    assert len(verdicts) == 1
    print(f"| {label} | {closed}/{len(rows)} | {terminal}/{len(rows)} | {decisions[verdicts.pop()]} |")
