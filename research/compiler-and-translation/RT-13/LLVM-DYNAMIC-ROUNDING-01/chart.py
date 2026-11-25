"""Render the per-route dynamic rounding and exception observations."""
import json
from pathlib import Path

data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Pipeline | Route | Value mismatches | Flag mismatches |")
print("| --- | --- | ---: | ---: |")
for profile, record in data["profiles"].items():
    for route, counts in record["counts"].items():
        print(f'| {profile} | {route} | {counts["value_mismatches"]} | {counts["flag_mismatches"]} |')
