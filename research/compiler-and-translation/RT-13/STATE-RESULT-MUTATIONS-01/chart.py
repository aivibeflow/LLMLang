#!/usr/bin/env python3
"""Render coverage of each observation projection and generator."""

import json
from pathlib import Path

report = json.loads(Path(__file__).with_name("evidence.json").read_text())
print("| Mutation | Result | Cell | Result and cell | Event multiset | Ordered observation |")
print("| --- | ---: | ---: | ---: | ---: | ---: |")
for mutation, counts in report["corpora"]["bounded_exhaustive"]["differences"].items():
    columns = " | ".join(str(counts[key]) for key in
                         ("result", "cell", "result_and_cell", "event_multiset", "complete"))
    print(f"| `{mutation}` | {columns} |")
print()
print("| Corpus | Program/cell pairs | Mutant comparisons | Detected mutations |")
print("| --- | ---: | ---: | ---: |")
for corpus, data in report["corpora"].items():
    detected = sum(bool(counts["complete"]) for counts in data["differences"].values())
    print(f"| `{corpus}` | {data['source_initial_profiles']} | {data['checked_mutant_observations']} | {detected} |")
