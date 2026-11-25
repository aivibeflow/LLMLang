#!/usr/bin/env python3
"""Render native extrema policy and operand-order differences."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
labels = {"glibc": "glibc", "sse2": "x86 SSE2", "rust": "Rust", "node": "Node", "python": "CPython"}
policies = ("propagate", "prefer_number", "prefer_number_left", "prefer_number_right", "ordered_left", "unordered_right",
            "signal_propagates_right")
print("| Native family | Propagate NaN | Prefer number | Prefer number, left tie | Prefer number, right tie | Ordered left | Unordered right | Propagate signaling, right tie |")
print("|---|---:|---:|---:|---:|---:|---:|---:|")
for family, row in ledger["metrics"].items():
    counts = row["policy_mismatches"]
    print(f"| {labels[family]} | " + " | ".join(str(counts[policy]) for policy in policies) + " |")
print()
print("| Native family | Operand swaps changing bits | Operand swaps changing numeric observation |")
print("|---|---:|---:|")
for family, row in ledger["metrics"].items():
    print(f"| {labels[family]} | {row['unordered_pairs_changing_bits_on_swap']} | "
          f"{row['unordered_pairs_changing_numeric_on_swap']} |")
