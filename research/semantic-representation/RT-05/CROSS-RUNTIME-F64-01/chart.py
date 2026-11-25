#!/usr/bin/env python3
"""Render F64 admission and native bit-copy measurements."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
labels = {"exact_bits": "Tagged exact bits", "canonical_nan": "Canonical NaN with signed zero",
          "same_value_zero": "SameValueZero quotient", "json_number": "Ordinary JSON number"}
metrics = ("accepted", "refused", "changed_literal_bits", "changed_numeric_observations", "merged_literal_pairs",
           "merged_numerically_distinct_pairs")
print("| Identity and wire policy | Accepted | Refused | Changed literal bits | Changed numeric vectors | Merged literal pairs | Merged numerically distinct pairs |")
print("|---|---:|---:|---:|---:|---:|---:|")
for key, counts in ledger["metrics"].items():
    print(f"| {labels[key]} | " + " | ".join(str(counts[name]) for name in metrics) + " |")
print()
print("| Native profile | Changed after scalar bit copy | Changed after array round trip |")
print("|---|---:|---:|")
profiles = {"node_default": "Node default", "node_jitless": "Node without JIT", "rust_O0": "Rust O0",
            "rust_O3": "Rust O3", "python": "CPython"}
for key, row in ledger["native_bit_copy_drifts"].items():
    print(f"| {profiles[key]} | {row['scalar']} | {row['boxed']} |")
