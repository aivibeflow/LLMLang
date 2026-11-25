"""Render blocking behavior from the eight unclosed-candidate trials."""
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Operation | Hooks observing an unclosed tree | Git exit | Unclosed tree committed to target branch |")
print("| --- | --- | ---: | --- |")
for row in ledger["results"]:
    if row["candidate_graph"] == "unclosed":
        hooks = ", ".join(f'`{item["hook"]}`' for item in row["hooks"])
        print(f'| `{row["operation"]}` | {hooks} | {row["git_status"]} | '
              f'{"yes" if row["candidate_installed"] else "no"} |')
