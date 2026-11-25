#!/usr/bin/env python3
"""Render the exact-evidence outcomes by conformance class."""

from collections import Counter
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Class | Conforming | Refuted | Pending |")
print("| --- | ---: | ---: | ---: |")
for name in ledger["classes"]:
    stats = Counter(case["expected"] for case in ledger["evidence_cases"] if case["class"] == name)
    print(f'| {name} | {stats["conforming"]} | {stats["refuted"]} | {stats["pending"]} |')
