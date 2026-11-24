"""Render driver outcomes and graph validation as a Markdown table."""
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Git operation | Policy | Context | Exit | Unmerged paths | Graph from Git index |")
print("| --- | --- | --- | ---: | ---: | --- |")
for row in ledger["results"]:
    fields = (row["operation"], row["policy"], row["context"], row["git_status"],
              len(row["unmerged"]), row["assembled_graph"] or "pending")
    print("| " + " | ".join(map(str, fields)) + " |")
