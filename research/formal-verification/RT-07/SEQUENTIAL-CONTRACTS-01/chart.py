#!/usr/bin/env python3
"""Render the finite comparison of sequence handoff rules."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
labels = {
    "all_successful": "Require all successful intermediate states",
    "some_successful": "Accept one suitable success",
    "all_final_states": "Require all states including errors",
    "unchecked": "Skip handoff check",
}
print("| Handoff rule | Admitted | False admissions | False refusals |")
print("| --- | ---: | ---: | ---: |")
for name, info in ledger["gates"].items():
    print(f'| {labels[name]} | {info["admitted"]} | {info["false_admission"]} | {info["false_refusal"]} |')
