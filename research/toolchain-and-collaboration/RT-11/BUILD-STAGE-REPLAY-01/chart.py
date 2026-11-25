#!/usr/bin/env python3
"""Render exact action counts and fresh median times from the replay."""

import json
from pathlib import Path

record = json.loads(Path(__file__).with_name("evidence.json").read_text())
verification = record["verification"]
print("| Stage | Forced compiles | Incremental compiles | Content compiles | Content hits |")
print("| --- | ---: | ---: | ---: | ---: |")
for stage, data in verification["exact_by_stage_and_method"].items():
    commands = [data[method]["compiled"] for method in ("clean", "incremental", "content")]
    print(f"| `{stage}` | " + " | ".join(map(str, [*commands, data["content"]["hits"]])) + " |")
print()
print("| Stage | Forced median (ms) | Incremental median (ms) | Content median (ms) |")
print("| --- | ---: | ---: | ---: |")
for stage, data in verification["fresh_median_ns"].items():
    medians = [data[method] / 1e6 for method in ("clean", "incremental", "content")]
    print(f"| `{stage}` | " + " | ".join(f"{sample:.3f}" for sample in medians) + " |")
