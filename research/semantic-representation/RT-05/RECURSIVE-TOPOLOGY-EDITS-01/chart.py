#!/usr/bin/env python3
"""Render the address-reuse comparisons by projection."""

import json
from pathlib import Path

data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
labels = {
    "keyed": "Keyed SCC",
    "structural": "Structural SCC",
    "body-only": "Local body only",
    "snapshot": "Whole snapshot",
}
print("| Address rule | Retained | Changed correctly | Stale | Unnecessary change |")
print("| --- | ---: | ---: | ---: | ---: |")
for policy, row in data["policies"].items():
    print(f'| {labels[policy]} | {row["retained"]} | {row["invalidations"]} | '
          f'{row["stale"]} | {row["unnecessary"]} |')
