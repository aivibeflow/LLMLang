#!/usr/bin/env python3
"""Render coverage and projection controls for declared observations."""

import json
from pathlib import Path

counts = json.loads(Path(__file__).with_name("evidence.json").read_text())["counts"]
print("| Decision | Count |")
print("| --- | ---: |")
for key, label in (
    ("profiles", "Profile/observation comparisons"),
    ("matches", "Matches of all required fields"),
    ("different", "Definite difference"),
    ("incomplete", "Incomplete observations"),
    ("shared_only_false_admissions", "False admissions from checking shared fields only"),
    ("terminal_only_misses_definite_full_profile_difference", "Definite differences missed by return/error only"),
):
    print(f"| {label} | {counts[key]} |")
