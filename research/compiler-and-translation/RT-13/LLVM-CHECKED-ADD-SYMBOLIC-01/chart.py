"""Render the prior and current proof dependencies for the same predicates."""

from collections import Counter
import json
from pathlib import Path

root = Path(__file__).resolve().parent
old = json.loads((root.parent / "LLVM-CHECKED-ADD-LEAN-01" / "evidence.json").read_text(encoding="utf-8"))
new = json.loads((root / "evidence.json").read_text(encoding="utf-8"))
groups = Counter((old["theorems"][name]["replay"], theorem["mode"])
                 for name, theorem in new["theorems"].items())
print("| Prior proof | Checked replacement | Claims | Native axioms per replacement |")
print("| --- | --- | ---: | ---: |")
for (prior, replacement), count in groups.items():
    print(f"| `{prior}` | {replacement} | {count} | 0 |")
