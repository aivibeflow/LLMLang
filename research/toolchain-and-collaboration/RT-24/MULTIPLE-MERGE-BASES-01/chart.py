"""Render native and real-base results for the seven merge scenarios."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Scenario | Forced A | Forced B | Default Git | All-base gate publishes |")
print("| --- | --- | --- | --- | --- |")
for row in ledger["rows_per_backend"]:
    if row["orientation"] != "left_first":
        continue
    results = [row["case"], row["by_base"]["A"]["status"], row["by_base"]["B"]["status"],
               row["native"]["status"], "yes" if row["published_commit"] else "no"]
    print("| " + " | ".join(results) + " |")
