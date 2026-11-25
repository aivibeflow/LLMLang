#!/usr/bin/env python3
"""Render Boolean evaluation differences by the first differing observation."""

import json
from pathlib import Path

evidence = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
names = {
    "agree": "Complete observation equal",
    "result_or_error": "Result or error differs",
    "final_state_only_after_result": "Same result, different final state",
    "ordered_trace_only": "Same result and state, different ordered trace",
}
print("| Comparison | Cases |")
print("| --- | ---: |")
for key, label in names.items():
    print(f'| {label} | {evidence["mode_comparisons"][key]} |')
