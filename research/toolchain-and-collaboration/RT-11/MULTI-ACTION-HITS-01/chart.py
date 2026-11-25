#!/usr/bin/env python3
"""Render hit rates by action and stage for the two exact cache routes."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
kinds = ("compile", "archive", "link", "verify")
print("| Stage | Compile | Archive | Link | Verify | Producer-key route total |")
print("| --- | ---: | ---: | ---: | ---: | ---: |")
for stage, policies in ledger["phases"].items():
    exact = policies["exact_payload"]
    coarse = policies["producer_keys"]
    ratios = " | ".join(f"{exact['hits'][kind]}/{exact['actions'][kind]}" for kind in kinds)
    predecessor = f"{sum(coarse['hits'].values())}/{sum(coarse['actions'].values())}"
    print(f"| `{stage}` | {ratios} | {predecessor} |")
