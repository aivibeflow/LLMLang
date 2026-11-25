"""Render the native, full and thin link results for downward cancellation."""
import json
from pathlib import Path

data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Version and link | Literal inline | Kept call | Inline with volatile inputs |")
print("| --- | --- | --- | --- |")
for name, row in data["profiles"].items():
    paths = ("inline_literals", "keep_call", "inline_loads")
    values = ["-0" if row["results"][f"downward/0/{path}"] == "8000000000000000" else "+0" for path in paths]
    print(f"| {name} | {' | '.join(values)} |")
