"""Render exact natural and negative input fuel coverage from the ledger."""
import json
from pathlib import Path

data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| SPG encoding | Returned with sufficient fuel | Nonnegative exhaustion | Negative exhaustion |")
print("| --- | ---: | ---: | ---: |")
for scope, profile in data["profiles"].items():
    observed = profile["counts"]
    print(f'| {scope} | {observed["in_budget"]} | {observed["nonnegative_exhausted"]} | {observed["negative_exhausted"]} |')
