#!/usr/bin/env python3
"""Render stale values and caller text sizes from the native binding fixture."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Optimization | Stale inlined results | Stale static-linked results | Stale trait-object results | Stale dictionary results |")
print("|---|---:|---:|---:|---:|")
for opt, routes in ledger["metrics"].items():
    print(f"| O{opt} | " + " | ".join(f"{routes[route]:,}" for route in ("static", "linked", "trait", "dictionary")) + " |")
print()
print("| Optimization | Inlined caller text, bytes | Static-linked caller text, bytes | Trait-object caller text, bytes | Dictionary caller text, bytes |")
print("|---|---:|---:|---:|---:|")
for opt, variants in ledger["artifacts"].items():
    artifact = variants["original"]
    sizes = artifact["wrapper_text_bytes"]
    inline = sizes["static"] + sum(artifact["specialization_text_bytes"]["inline"])
    linked = sizes["linked"] + sum(artifact["specialization_text_bytes"]["linked"])
    print(f"| {opt} | {inline} | {linked} | {sizes['trait']} | {sizes['dictionary']} |")
