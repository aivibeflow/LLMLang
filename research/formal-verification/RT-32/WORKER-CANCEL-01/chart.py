#!/usr/bin/env python3
"""Render the checked worker claims and bounded archive replay."""

import json
from pathlib import Path

entry = json.loads(Path(__file__).with_name("evidence.json").read_text())
checks = {
    "General checked properties": len(entry["generic_and_counterexample_axioms"]) - 2,
    "Checked policy counterexamples": 2,
    "Rejected late-cancel proof": int(entry["incorrect_late_cancellation_proof"] == "rejected"),
    "Exact archive schedule equalities": len(entry["archive_equalities"]),
    "Archived worker handoffs checked": entry["guarded_steps"],
    "Archived terminal job outcomes checked": entry["guarded_terminal_outcomes"],
}
print("| Evidence | Count |")
print("|---|---:|")
for name, count in checks.items():
    print(f"| {name} | {count} |")
