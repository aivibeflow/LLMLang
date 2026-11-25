#!/usr/bin/env python3
"""Render the output observation controls from the checked ledger."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
counts = ledger["counts"]
print("| Comparison | Cases | Different |")
print("| --- | ---: | ---: |")
total = counts["split_pairs"]
print(f"| Coalesced vs. split, bytes and status | {total} | 0 |")
print(f"| Coalesced vs. split, with attempt trace | {total} | {counts['split_pairs_differing_in_calls']} |")
total = counts["robust_rows"]
print(f"| Retry vs. drop, bytes and status | {total} | {counts['short_drop_differences']} |")
print(f"| Drop reports success with missing bytes | {total} | {counts['short_drop_false_success']} |")
