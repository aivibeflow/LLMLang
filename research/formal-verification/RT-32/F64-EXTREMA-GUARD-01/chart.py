#!/usr/bin/env python3
"""Render the exact F64 substitution guard evidence."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
archive = len(ledger["archive_equalities"])
counts = (
    ("Audited model declarations", len(ledger["model_theorem_axioms"])),
    ("Kernel-checked native pair equations", archive),
    ("Archived native policy vectors", archive * len(ledger["native_policy_map"])),
    ("Guard admitted pairs", ledger["guard_admitted_in_archive"]),
    ("Guard refused pairs", ledger["guard_refused_in_archive"]),
    ("Refused unguarded substitution proofs", int(ledger["false_unguarded_substitution_proof"] == "rejected")),
)
print("| Checked result | Count |")
print("|---|---:|")
for label, count in counts:
    print(f"| {label} | {count:,} |")
