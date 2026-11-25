#!/usr/bin/env python3
"""Render adapter controls against the required signed division observation."""

import json
from pathlib import Path

evidence = json.loads(Path(__file__).with_name("evidence.json").read_text())
print("| Variant | Input pairs | Different required observations |")
print("| --- | ---: | ---: |")
for name, count in evidence["differences_from_required_outcome"].items():
    print(f"| `{name}` | {evidence['input_pairs_per_variant']} | {count} |")
