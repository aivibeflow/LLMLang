#!/usr/bin/env python3
"""Render mismatches exposed by each observation projection."""

import json
from pathlib import Path

observed = json.loads(Path(__file__).with_name("evidence.json").read_text())["native"]["differences"]
print("| Control | Status | Status and cell | Ordered observation |")
print("| --- | ---: | ---: | ---: |")
for case, metrics in observed.items():
    print(f"| `{case}` | {metrics['status']} | {metrics['status_and_cell']} | {metrics['complete']} |")
