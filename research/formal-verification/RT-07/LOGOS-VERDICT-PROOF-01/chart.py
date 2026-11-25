"""Render transitive axiom counts from the exact proof audit."""

import json
from pathlib import Path

audit = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Lean theorem | Standard axioms | Native computation axioms | Total |")
print("| --- | ---: | ---: | ---: |")
for name, dependencies in audit["theorems"].items():
    label = name.removeprefix("LLMLang.LogosScalarDenotation.")
    print(f"| `{label}` | {len(audit['standard_axioms'])} | "
          f"{dependencies['native_decide_axioms']:,} | {dependencies['total_axioms']:,} |")
