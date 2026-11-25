#!/usr/bin/env python3
"""Render the observed changes caused by leading blank lines."""

import json
from pathlib import Path

data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
names = {
    "pure-plain": "Constant, no DWARF",
    "pure-debug": "Constant, DWARF",
    "line-plain": "__LINE__, no DWARF",
    "line-debug": "__LINE__, DWARF",
}
print("| Profile | Exact object | Machine code bytes | Source location | Native output |")
print("| --- | --- | --- | --- | --- |")
for profile, comparisons in data["comparison_to_baseline"].items():
    changed = comparisons["leading-lines"]
    statuses = ["same" if changed[key] else "changed"
                for key in ("object_sha256", "text_sha256", "machine_location", "observations")]
    print(f'| {names[profile]} | {" | ".join(statuses)} |')
