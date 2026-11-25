#!/usr/bin/env python3
"""Render exact Git archive storage and edit measurements."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
names = {"packed": "Packed entries", "per_entry": "Per-entry content-addressed files"}
print("| Layout | Baseline files | Baseline uncompressed bytes | New blobs after edit | New uncompressed bytes | Removed paths |")
print("|---|---:|---:|---:|---:|---:|")
for row in ledger["measurements"]:
    base, edit = row["baseline_size"], row["edit_cost"]
    print(f'| {names[row["layout"]]} | {base["files"]} | {base["bytes"]:,} | '
          f'{edit["added_blob_count"]} | {edit["added_uncompressed_bytes"]:,} | {edit["removed_path_count"]} |')
