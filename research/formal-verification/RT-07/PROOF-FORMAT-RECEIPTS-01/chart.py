#!/usr/bin/env python3
"""Render checks and receipt-reuse controls for the proof format fixture."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
print("| Query | Artifact | Lean source | CPC text |")
print("| ---: | ---: | --- | --- |")
for row in ledger["proof_checks"]:
    formats = " | ".join(check["status"] for check in row["checks"].values())
    print(f"| {row['query_literal']} | {row['artifact_literal']} | {formats} |")
print()
print("| Reuse control | Decision |")
print("| --- | --- |")
for name, decision in ledger["reuse_controls"].items():
    print(f"| `{name}` | {decision} |")
