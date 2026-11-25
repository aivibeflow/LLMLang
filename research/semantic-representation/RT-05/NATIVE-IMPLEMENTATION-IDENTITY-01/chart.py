#!/usr/bin/env python3
"""Render the experiment's categorical comparison as a Markdown table."""

import json
from pathlib import Path

data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
rows = data["rows"]
pairs = len(rows) * (len(rows) - 1) // 2
labels = {
    "caller_only_key": "Caller bytes alone",
    "implementation_key": "Resolved implementation",
    "fixture_evidence_key": "Fixture evidence",
}
print("| Projection | Profile pairs with distinct native vectors and the same key |")
print("| --- | ---: |")
for field, count in data["pairs_with_same_key_and_distinct_observations"].items():
    print(f"| {labels[field]} | {count}/{pairs} |")
