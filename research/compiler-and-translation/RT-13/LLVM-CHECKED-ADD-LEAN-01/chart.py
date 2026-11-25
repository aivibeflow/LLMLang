"""Render Lean replay modes and exact nonstandard axiom counts."""

from collections import defaultdict
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
counts = defaultdict(list)
for theorem in ledger["theorems"].values():
    counts[theorem["replay"]].append(sum("._native.bv_decide." in name for name in theorem["axioms"]))
print("| Replay mode | Theorems | Native axioms per theorem |")
print("| --- | ---: | ---: |")
for mode, values in counts.items():
    assert len(set(values)) == 1
    print(f"| `{mode}` | {len(values)} | {values[0]} |")
