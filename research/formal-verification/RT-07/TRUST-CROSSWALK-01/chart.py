#!/usr/bin/env python3
"""Render claim-specific proof bases and the strict policy projection."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
print("| Claim | Native axioms | Explicit open premises | Recorded result |")
print("| --- | ---: | ---: | --- |")
for name, request in ledger["claims"].items():
    print(f"| `{name}` | {request['native_count']} | {len(request['open_premises'])} | "
          f"{ledger['strict_policy_projection'][name]} |")
