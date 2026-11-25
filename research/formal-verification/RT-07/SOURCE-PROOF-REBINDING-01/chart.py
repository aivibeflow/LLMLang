#!/usr/bin/env python3
"""Render exact gate outcomes by source mutation."""

import json
from pathlib import Path

rows = json.loads(Path(__file__).with_name("evidence.json").read_text())["controls"]
print("| Source case | Reuse old wire | Reuse old proof with fresh wire | Check rebuilt proof |")
print("| --- | --- | --- | --- |")
for row in rows:
    fresh = row["fresh_wire_check"].split(":")[0]
    print(f"| `{row['name']}` | {row['old_wire_check']} | {fresh} | {row['rebound_proof_check'] or 'untried'} |")
