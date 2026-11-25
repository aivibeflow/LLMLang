"""Render checked proof counts from the replay ledger."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Checked statement | Theorems | Input coverage |")
print("| --- | ---: | --- |")
print(f"| Exact source observation | {ledger['source_agreement']} | 16 inputs per program |")
print(f"| Resource completion | {ledger['resource_completion']} | 16 inputs per program |")
print(f"| Mutated graph differs | {ledger['mutation_inequalities']} | One witness per mutation |")
