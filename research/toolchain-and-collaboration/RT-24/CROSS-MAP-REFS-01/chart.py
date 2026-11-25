#!/usr/bin/env python3
"""Render publication and freshness outcomes from the native Git ledger."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text())
labels = {
    "old_own_only": "Old decision and own-ref CAS",
    "strict_refs": "Verify both originally observed refs",
    "fresh_unverified": "Recheck current peer and verify only own ref",
    "fresh_verified": "Recheck current peer and verify both refs",
}
print("| Publication policy | Accepted changes | Ineligible publications | Valid changes refused |")
print("|---|---:|---:|---:|")
for policy, values in ledger["metrics"].items():
    print(f'| {labels[policy]} | {values["published"]} | {values["ineligible_publication"]} | '
          f'{values["valid_proposal_refused"]} |')
