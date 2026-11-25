#!/usr/bin/env python3
"""Render the F64 to I64 policy comparison from its native ledger."""

import json
from pathlib import Path

LABELS = {
    "checked_trunc": "Checked truncation",
    "checked_integral": "Checked integral",
    "rust_saturate": "Rust saturating cast",
    "node_wrap_integral": "Node integral then wrap",
    "cpython_unbounded_int": "CPython unbounded integer",
}
FIELDS = ("accepted", "range", "fraction", "nonfinite", "different_from_checked_trunc")


def main():
    data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
    print("| Policy | Accepted | Range refusal | Fraction refusal | Nonfinite refusal | Different from checked truncation |")
    print("|---|---:|---:|---:|---:|---:|")
    for policy, label in LABELS.items():
        counts = data["metrics"][policy]
        rendered = " | ".join(str(counts[field]) for field in FIELDS)
        print(f"| {label} | {rendered} |")


if __name__ == "__main__":
    main()
