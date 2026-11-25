#!/usr/bin/env python3
"""Render entailed and underdetermined contract judgments by projection."""

import json
from pathlib import Path

report = json.loads(Path(__file__).with_name("evidence.json").read_text())
print("| Projection | Claims | Entailed | Existential false admissions | True of anchor but unestablished with every input recorded |")
print("| --- | ---: | ---: | ---: | ---: |")
for name, counts in report["by_projection"].items():
    columns = " | ".join(str(counts[key]) for key in (
        "claims", "entailed", "existential_false_admission", "complete_input_coverage_unestablished",
    ))
    print(f"| `{name}` | {columns} |")
