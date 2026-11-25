#!/usr/bin/env python3
"""Render output and rejection counts after successful initial admission."""

import json
from pathlib import Path

data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
names = {
    "pathname": "Reopen pathname",
    "descriptor": "Retain descriptor",
    "snapshot": "Retain verified byte snapshot",
    "revalidate": "Reopen and revalidate consumed bytes",
    "lease": "Cooperative read lease",
}
print("| Read policy | Exact bytes | Wrong bytes | Missing afterward | Final integrity refusal |")
print("| --- | ---: | ---: | ---: | ---: |")
for policy, results in data["counts"].items():
    counts = [str(results.get(outcome, 0)) for outcome in (
        "exact", "wrong-bytes", "missing-after-check", "failed-final-integrity",
    )]
    print(f'| {names[policy]} | {" | ".join(counts)} |')
