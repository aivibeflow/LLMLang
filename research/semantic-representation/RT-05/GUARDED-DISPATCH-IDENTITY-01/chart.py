"""Render safe reuse, stale reuse and conservative invalidation counts."""
import json
from pathlib import Path

data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Key | Safe reuse | Stale reuse | Conservative recomputation | Required recomputation |")
print("| --- | ---: | ---: | ---: | ---: |")
for name, row in data["counts"].items():
    safe, stale = row["safe_reuse"], row["stale_reuse"]
    conservative, required = row["conservative_miss"], row["required_recompute"]
    print(f"| {name} | {safe:,} | {stale:,} | {conservative:,} | {required:,} |")
