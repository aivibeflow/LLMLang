#!/usr/bin/env python3
"""Render context coverage for each declared observation projection."""

import json
from pathlib import Path

record = json.loads(Path(__file__).with_name("evidence.json").read_text())
print("| Profile | Provider/domain pairs | Client comparisons | Observationally indistinguishable |")
print("| --- | ---: | ---: | ---: |")
for profile, row in record["comparison_counts"].items():
    parts = (row["provider_domain_pairs"], row["context_comparisons"], row["contextually_indistinguishable"])
    print(f"| `{profile}` | " + " | ".join(map(str, parts)) + " |")
