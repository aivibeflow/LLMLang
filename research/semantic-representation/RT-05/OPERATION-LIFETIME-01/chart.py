#!/usr/bin/env python3
"""Render admissions, misdirections and denials for previously pinned calls."""

import json
from pathlib import Path

data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
labels = {
    "exact": "Exact published pair",
    "latest_stable_id": "Latest operation selected by stable ID",
    "original_alias": "Current owner of original alias",
    "selected_equal_value": "Current selection with equal operation bytes",
}
print("| Resolution policy | Wrong exact target | Unexpected denial | Unexpected admission |")
print("| --- | ---: | ---: | ---: |")
for policy, counts in data["resolution_comparison"].items():
    print(f'| {labels[policy]} | {counts["wrong_exact_target"]} | {counts["unexpected_denial"]} | '
          f'{counts["unexpected_execution"]} |')
