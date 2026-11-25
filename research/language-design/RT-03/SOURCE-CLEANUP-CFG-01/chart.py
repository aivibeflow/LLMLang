"""Render outcome and coverage comparisons for the bounded source study."""

import json
from pathlib import Path

run = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| CFG comparison | Any | Trace | Return | Error causes | Resource state | Handle owner |")
print("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
for name, counts in run["mismatches"].items():
    columns = ("any", "trace", "result", "errors", "slots", "handle")
    values = " | ".join(str(counts[column]) for column in columns)
    print(f"| {name} | {values} |")
