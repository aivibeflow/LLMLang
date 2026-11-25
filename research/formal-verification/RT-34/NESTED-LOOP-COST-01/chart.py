"""Render cost-bound precision and functional-equivalence controls."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Cost profile | Inputs | Rectangular overcounts | Dependent overcounts | Guard-omission undercounts | Extra work, same result |")
print("| --- | ---: | ---: | ---: | ---: | ---: |")
for profile, result in ledger["candidate_results"].items():
    values = " | ".join(str(value) for value in result.values())
    print(f"| {profile} | {ledger['lean_observations']} | {values} |")
