#!/usr/bin/env python3
"""Render CLI corpus outcomes and rejected semantic mutations."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
routes = {
    "host_python": "Existing Python host reference",
    "host_c": "Existing C host reference",
    "interpreted": "Typed recipe interpreter",
    "rust_O0": "Generated Rust O0",
    "rust_O3": "Generated Rust O3",
}
print("| Route | Accepted cases |")
print("|---|---:|")
for key, count in ledger["route_counts"].items():
    print(f'| {routes[key]} | {count}/{ledger["case_count"]} |')
print()
print("| Semantic mutation | Cases rejected in each candidate route |")
print("|---|---:|")
for key, result in ledger["controls"].items():
    title = key.replace("_", " ").capitalize()
    print(f'| {title} | {len(result["rejected_case_ids"])} |')
