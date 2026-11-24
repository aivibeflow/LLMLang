"""Render conflict path counts as a Markdown table from the evidence ledger."""
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Case | Tool | Unmerged paths before | Unmerged paths after |")
print("| --- | --- | ---: | ---: |")
for row in ledger["results"]:
    print(f'| {row["case"]} | {row["adapter"] or "native Git"} | {len(row["before"])} | {len(row["after"])} |')
