#!/usr/bin/env python3
"""Render the key reuse outcome counts from the finite ledger."""

import json
from pathlib import Path

data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
names = {
    "local_body": "Local body",
    "exact_subject": "Exact implementation subject",
    "resolved_execution": "Subject with resolved bindings",
    "whole_state": "Whole state",
}
print("| Key | Safe reuse | Stale reuse | Missed reuse |")
print("| --- | ---: | ---: | ---: |")
for key, counts in data["comparison"].items():
    print(f'| {names[key]} | {counts["safe_reuse"]} | {counts["stale_reuse"]} | {counts["missed_reuse"]} |')
