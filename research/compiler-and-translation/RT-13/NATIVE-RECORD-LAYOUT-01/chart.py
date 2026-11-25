#!/usr/bin/env python3
"""Render the measured results of each ABI and behavior gate."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
labels = {
    "symbol": "Symbol",
    "size_alignment": "Size and alignment",
    "descriptor": "Provider descriptor",
    "verified_direct": "Binary-verified direct layout",
    "verified_adapter": "Binary-verified layout adapter",
    "exact_behavior": "Layout adapter plus exact native observations",
}
print("| Admission gate | Accepted artifacts | Incorrect accepted vectors |")
print("|---|---:|---:|")
for gate, result in ledger["rollup"].items():
    tested = result["accepted"] * ledger["vectors_per_route"]
    print(f'| {labels[gate]} | {result["accepted"]}/{ledger["artifact_count"]} | {result["wrong_vectors"]}/{tested} |')
