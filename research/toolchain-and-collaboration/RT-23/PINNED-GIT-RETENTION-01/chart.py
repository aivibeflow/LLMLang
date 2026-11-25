"""Render native retention outcomes from the replayable ledger."""
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Backend and read policy | After rewrite and collection | After final retention ref is gone |")
print("| --- | --- | --- |")
for name, row in ledger["cases"].items():
    retained = "Exact old root" if row["after_gc"] is not None else "Missing commit"
    released = "Exact old root" if row["after_release_and_gc"] is not None else "Missing commit"
    print(f"| {name} | {retained} | {released} |")
