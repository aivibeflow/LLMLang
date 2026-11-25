#!/usr/bin/env python3
"""Render recovery and false-success counts from the native Linux ledger."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
names = {"blind_retry": "Blind retry", "latest_payload": "Latest payload", "exact_log": "Exact framed operation"}
print("| Recovery policy | Reported successes | Wrong successes | Duplicate records | Refused calls |")
print("|---|---:|---:|---:|---:|")
for policy, row in ledger["metrics"].items():
    print(f'| {names[policy]} | {row["successful_calls"]} | {row["wrong_successes"]} | '
          f'{row["duplicate_records"]} | {row["refusals"]} |')
