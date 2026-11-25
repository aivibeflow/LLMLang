#!/usr/bin/env python3
"""Render scope-binding failures from the recorded solver comparison."""

import json
from pathlib import Path

counts = json.loads(Path(__file__).with_name("evidence.json").read_text())["proof_reuse"]
print("| Comparison | Count |")
print("| --- | ---: |")
for field, label in (
    ("same_command_uses", "Same command text"),
    ("exact_context_matches", "Exact context"),
    ("wrong_context_with_sat_witness", "Wrong context with a satisfying witness"),
    ("wrong_context_also_unsat", "Wrong context also independently unsatisfiable"),
    ("same_session_same_command_uses", "Same session and command"),
    ("wrong_context_with_sat_witness_in_same_session", "Wrong context with a witness in the same session"),
):
    print(f"| {label} | {counts[field]} |")
