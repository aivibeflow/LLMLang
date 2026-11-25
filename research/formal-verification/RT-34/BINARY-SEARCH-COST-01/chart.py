"""Render discriminators for the two binary-search input families."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Shape | Cases | Floor-log undercounts | Linear bound overcounts | One test per probe undercounts | Mutant nonhalving | Mutant stalls |")
print("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
fields = ("corrected_search_cases", "log_floor_under_counts", "linear_bound_loose",
          "one_condition_per_probe_under_counts", "mutant_nonhalving", "mutant_stalled")
for name, stats in ledger["profiles"].items():
    values = " | ".join(f"{stats[field]:,}" for field in fields)
    print(f"| {name} | {values} |")
