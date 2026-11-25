"""Render identity disagreements relative to native observations."""

import json
from pathlib import Path

run = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Identity input | Different trace, same key | Same trace, different key | Same trace, same key |")
print("| --- | ---: | ---: | ---: |")
for policy, counts in run["counts"].items():
    fields = ("different_observation_same_key", "same_observation_distinct_key",
              "same_observation_same_key")
    values = " | ".join(str(counts.get(field, 0)) for field in fields)
    print(f"| {policy} | {values} |")
