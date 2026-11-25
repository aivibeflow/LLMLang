#!/usr/bin/env python3
"""Render resource lifetime and cancellation results per native configuration."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
names = {
    "guarded": "Guarded write and terminal settlement",
    "admission_only": "Admission check only",
    "early_terminal": "Terminate at cancel request",
}
print("| Cancellation policy | Acquired / released | Writes attempted after revocation | Terminal with live handle | Wrong outcomes | Wrong file effects |")
print("|---|---:|---:|---:|---:|---:|")
for name, data in ledger["metrics_per_host_configuration"].items():
    print(f'| {names[name]} | {data["acquisitions"]}/{data["confirmed_releases"]} | '
          f'{data["write_attempts_after_revocation"]} | {data["early_terminal_live_handle"]} | '
          f'{data["wrong_outcomes"]} | {data["wrong_effects"]} |')
