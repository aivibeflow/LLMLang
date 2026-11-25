#!/usr/bin/env python3
"""Render the three demand comparisons from the evidence ledger."""

import json
from pathlib import Path

evidence = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
labels = {
    "snapshot": "Whole snapshot",
    "implementation_for_all": "Implementation key for every request",
    "metadata_without_subject": "Metadata keys without the checked subject",
    "typed": "Typed projections",
}
print("| Projection | Implementation | Verification | Navigation |")
print("| --- | ---: | ---: | ---: |")
for policy, counts in evidence["comparisons"].items():
    columns = [
        f'{counts[demand]["valid_reuse"]} / {counts[demand]["invalid_reuse"]} / {counts[demand]["missed_reuse"]}'
        for demand in ("implementation", "verification", "navigation")
    ]
    print(f'| {labels[policy]} | {" | ".join(columns)} |')
