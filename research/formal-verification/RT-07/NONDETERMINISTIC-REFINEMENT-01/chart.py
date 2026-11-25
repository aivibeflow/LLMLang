#!/usr/bin/env python3
"""Render observed refinement admissions over the finite graph family."""

import json
from pathlib import Path

data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))["counts"]
print("| Comparison | Ordered pairs |")
print("| --- | ---: |")
labels = {
    "explicit_refinement": "Explicit maximal outcomes admit",
    "terminal_refinement": "Terminal-only projection admits",
    "unsound_projected_admission": "Terminal-only admission rejected by explicit outcomes",
    "of_which_no_terminal_replacement": "Of those, replacement has no terminal outcome",
}
for field, label in labels.items():
    print(f"| {label} | {data[field]:,} |")
