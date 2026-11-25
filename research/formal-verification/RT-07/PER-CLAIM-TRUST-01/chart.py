#!/usr/bin/env python3
"""Render the candidate policy decisions from the theorem trust ledger."""

import json
from pathlib import Path

rows = json.loads(Path(__file__).with_name("evidence.json").read_text())["declarations"]
print("| Declaration | Kernel only | Reviewed imported premise | Native evaluation allowed |")
print("| --- | --- | --- | --- |")
for name, entry in rows.items():
    print(f"| `{name}` | " + " | ".join(entry["decisions"].values()) + " |")
