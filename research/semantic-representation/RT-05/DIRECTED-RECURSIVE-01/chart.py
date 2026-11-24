"""Render canonicalization collisions after dropping directed graph information."""
import json
from pathlib import Path

data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Dropped distinction | Colliding projected classes | Largest collapsed family |")
print("| --- | ---: | ---: |")
for mode, values in data["projections"].items():
    print(f'| {mode} | {values["collision_classes"]:,} | {values["largest_collapsed_family"]} |')
