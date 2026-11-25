#!/usr/bin/env python3
"""Render endpoint and callback contract outcomes."""

import json
from pathlib import Path

counts = json.loads(Path(__file__).with_name("evidence.json").read_text())["counts"]
print("| Check | Count |")
print("| --- | ---: |")
for key, label in (
    ("valid_endpoint_pairs", "Valid source/target pairs"),
    ("both_orders_safe", "Both update orders safe at an observer"),
    ("exactly_one_order_safe", "Exactly one safe update order"),
    ("admitted_profiles", "Admitted transition profiles"),
    ("refused_profiles", "Invalid endpoint profiles refused"),
    ("final_only_false_admissions", "Endpoint-only false admissions"),
    ("false_admissions_with_rollback", "False admissions despite rollback"),
):
    print(f"| {label} | {counts[key]} |")
