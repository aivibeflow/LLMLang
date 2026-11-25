#!/usr/bin/env python3
"""Render exact outcome reuse by environment projection."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
labels = {
    "subject_only": "Source subject and request",
    "successful_reads": "Successful reads only",
    "exact_scoped_read": "Exact consulted input",
    "parsed_observation": "Checked parsed observation",
    "whole_environment": "Whole captured environment",
}
print("| Projection | Safe reuse | Stale reuse | Missed reuse |")
print("| --- | ---: | ---: | ---: |")
for key, row in ledger["comparison"].items():
    print(f'| {labels[key]} | {row["safe"]} | {row["stale"]} | {row["missed"]} |')
