#!/usr/bin/env python3
"""Render kernel check and native fixed-probe evidence counts."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
controls = {"split_receiver_changes_trace", "changed_bias_changes_trace", "five_probes_miss_alias"}
model = ledger["model_theorem_axioms"]
assert controls <= set(model)
archive = len(ledger["archive_equalities"])
counts = (
    ("General model theorems", len(model) - len(controls)),
    ("Checked counterexamples", len(controls)),
    ("Exact archived class equations", archive),
    ("Archived recipe vectors checked", archive * len(ledger["archive_modes"]) * ledger["archive_recipes"]),
    ("Fixed probe equations checked", len(ledger["native_probe_equalities"])),
    ("New native probe vectors across four profiles", ledger["native_probe_vectors"]),
    ("Distinct signatures with six probes", ledger["native_distinct_full_probe_signatures"]),
    ("Distinct signatures with the first five probes", ledger["native_distinct_short_probe_signatures"]),
    ("Refused false equivalence proofs", int(ledger["false_equivalence"] == "rejected")),
)
print("| Checked result | Count |")
print("|---|---:|")
for label, count in counts:
    print(f"| {label} | {count:,} |")
