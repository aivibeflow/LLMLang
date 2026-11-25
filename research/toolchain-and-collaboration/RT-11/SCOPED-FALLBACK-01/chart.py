#!/usr/bin/env python3
"""Render the fallback work and outcome counts from the simulation."""

import json
from pathlib import Path

data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
names = {"optimistic": "Optimistic recorded-edge reuse",
         "whole_graph": "Whole-graph fallback", "scoped": "Scoped fallback"}
print("| Policy | Executed actions | Admitted packages | Stale packages | Stale available results |")
print("| --- | ---: | ---: | ---: | ---: |")
for key, counts in data["policies"].items():
    executed = counts["compute"] + counts["compute_ephemeral"]
    print(f'| {names[key]} | {executed} | {counts["packages_admitted"]} | '
          f'{counts["stale_packages"]} | {counts["stale_results"]} |')
