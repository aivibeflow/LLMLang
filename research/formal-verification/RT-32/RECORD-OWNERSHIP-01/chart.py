#!/usr/bin/env python3
"""Render scoped theorem and archive checks from the Lean verification ledger."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
counterexamples = {
    "duplicateDeclarationRepeatsRelease",
    "mismatchedDeclarationsCanInventRelease",
    "oppositeCompletionOrdersDistinguishTrace",
}
checked = set(ledger["checked_theorems"])
print("| Evidence | Count |")
print("|---|---:|")
rows = {
    "General ownership theorems": len(checked - counterexamples),
    "Checked counterexamples": len(checked & counterexamples),
    "Rejected proof applications": len(ledger["rejected_proof_applications"]),
    "Generated archive equalities": ledger["archive_equalities"],
    "Early-exit vectors in the equalities": ledger["phase_counts"]["early_exit"],
    "Completed vectors in the equalities": ledger["phase_counts"]["completed"],
    "Native executions represented": ledger["native_measurements_represented"],
}
for name, count in rows.items():
    print(f"| {name} | {count:,} |")
