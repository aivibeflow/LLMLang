"""Render native merge coverage and fresh fallback outcomes."""
import json
from pathlib import Path

data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Native merge | Provider-only coverage | State-bound coverage | Fresh check | Publication |")
print("| --- | --- | --- | --- | --- |")
for name, row in data["cases"].items():
    print(f'| {name} | {row["provider_only_receipts"]} | {row["state_bound_receipts"]} | '
          f'{row["fresh_validation"]} | {row["publication_and_retry"]["outcome"]} |')
