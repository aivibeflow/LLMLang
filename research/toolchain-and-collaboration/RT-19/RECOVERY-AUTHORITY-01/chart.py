#!/usr/bin/env python3
"""Render authorization and recovery results from the Linux/SQLite ledger."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
names = {
    "prepared_authority": "Prepared authority",
    "blanket_fresh": "Fresh read and write for every result",
    "split_fresh": "Separate fresh rights without fence",
    "split_fenced": "Separate fresh rights with SQLite writer fence",
}
print("| Recovery policy | Proof results | Unauthorized effects | Unauthorized disclosures | Valid historical result denied |")
print("|---|---:|---:|---:|---:|")
for policy, row in ledger["metrics"].items():
    print(f'| {names[policy]} | {row["proof_returned"]} | {row["unauthorized_effect"]} | '
          f'{row["unauthorized_disclosure"]} | {row["valid_historical_result_denied"]} |')
