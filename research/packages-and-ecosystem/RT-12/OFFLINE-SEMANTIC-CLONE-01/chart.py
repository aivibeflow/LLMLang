#!/usr/bin/env python3
"""Render the retained and unavailable closure controls."""

import json
from pathlib import Path

data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Control | Outcome | Verified objects |")
print("| --- | --- | ---: |")
for row in data["cases"]:
    print(f'| {row["case"]} | {row["outcome"]} | {len(row.get("objects", ())) } |')
