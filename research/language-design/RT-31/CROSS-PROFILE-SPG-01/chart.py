"""Render exact profile coverage and generated source sizes as Markdown."""
import json
from pathlib import Path
from statistics import median

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Profile | Bodies | Minimum bytes | Median bytes | Maximum bytes |")
print("| --- | ---: | ---: | ---: | ---: |")
for name in ledger["profiles"]:
    sizes = [profile["bytes"] for row in ledger["cases"] for profile in row["profile_sources"]
             if profile["profile"] == name]
    print(f"| `{name}` | {len(sizes)} | {min(sizes)} | {median(sizes):g} | {max(sizes)} |")
