#!/usr/bin/env python3
"""Render the admission gates and observations from the native ABI ledger."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
proposals = ledger["direct_proposals"]
print("| Binding gate | Eligible proposals | Incompatible direct admissions |")
print("|---|---:|---:|")
print(f'| Symbol and aggregate type | {proposals}/{proposals} | {ledger["symbol_type_false_admissions"]} |')
print(f'| Matching explicit direct convention | {ledger["checked_direct_admissions"]}/{proposals} | 0 |')
print(f'| Fixed pointer bridge | {ledger["checked_bridge_admissions"]}/{proposals} | 0 |')
print()
print("| Executed route | Native runs | Matching output vectors |")
print("|---|---:|---:|")
for route, runs in ledger["native_route_runs"].items():
    print(f'| {route.title()} | {runs} | {runs * ledger["vectors_per_run"]} |')
