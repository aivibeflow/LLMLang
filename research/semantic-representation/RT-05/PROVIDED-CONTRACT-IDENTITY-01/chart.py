#!/usr/bin/env python3
"""Render changes in conditional admission when only the declaration varies."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
name = {
    "general": "General",
    "parity": "Parity",
    "stay": "Stay only",
    "advance": "Advance only",
    "permits-mixed": "Also permits mixed result",
    "omits-255": "Omits input 255",
}
print("| Provided declaration | Body check | Refinement to general |")
print("| --- | --- | --- |")
for case in ledger["cases"]:
    if case["provider"] != "parity" or case["required"] != "general":
        continue
    results = ["pass" if case[k] is None else f"fails at {case[k]}"
               for k in ("body_first_failure", "refinement_first_failure")]
    print(f'| {name[case["provided"]]} | {" | ".join(results)} |')
