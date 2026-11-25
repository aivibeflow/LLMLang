"""Render LSP edit outcomes across each client validation policy."""
import json
from pathlib import Path

data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
outcomes = ("correct", "wrong", "range", "token", "occurrence", "version")
print("| Client | Correct | Wrong | Invalid range | Wrong token | Wrong occurrence | Stale version |")
print("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
for name, result in data["outcomes"].items():
    print(f"| {name} | " + " | ".join(str(result.get(outcome, 0)) for outcome in outcomes) + " |")
