"""Render user-space read and decode counts from the pinned container experiments."""
import json
from pathlib import Path

data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Layout | Initial hits | Metadata bytes | Payload bytes | Payload decodes |")
print("| --- | ---: | ---: | ---: | ---: |")
for layout, coverage in data["runs"].items():
    for hits, counts in coverage.items():
        print(f'| {layout} | {hits} | {counts["metadata"]:,} | {counts["payload"]:,} | {counts["decodes"]} |')
