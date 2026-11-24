"""Render safety and unnecessary rejection counts from the LSP action ledger."""
import json
from pathlib import Path

data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Policy | Stale applications | Applied with wrong behavior | Unnecessary rejections |")
print("| --- | ---: | ---: | ---: |")
for policy, counts in data["summaries"].items():
    print(f'| {policy} | {counts["staleApplications"]} | {counts["wrongBehavior"]} | {counts["unnecessaryRejections"]} |')
