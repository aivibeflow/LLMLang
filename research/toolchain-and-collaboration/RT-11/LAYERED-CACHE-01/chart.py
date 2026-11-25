#!/usr/bin/env python3
"""Render dispositions from the layered cache controls."""

import json
from pathlib import Path

data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Outcome | Controls |")
print("| --- | ---: |")
for status, count in data["counts"].items():
    print(f"| `{status}` | {count} |")
