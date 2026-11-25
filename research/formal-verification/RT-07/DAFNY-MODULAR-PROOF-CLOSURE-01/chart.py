"""Render modular verifier dispositions and CPC checker results."""

import json
from pathlib import Path

LABELS = {
    "caller_only": "Caller only, correct provider bytes",
    "caller_only_wrong_provider": "Caller only, wrong provider bytes",
    "closed": "Caller and correct provider",
    "wrong_provider_closure": "Caller and wrong provider",
    "resource_exhaustion": "Caller with resource limit 1",
}


def main():
    evidence = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
    print("| Dafny run | Verified units | Errors | Out of resource | Exit | Disposition |")
    print("|---|---:|---:|---:|---:|---|")
    for name, row in evidence["dafny"]["4.12.1"].items():
        print(f"| {LABELS[name]} | {row['verified']} | {row['errors']} | {row['out_of_resource']} | "
              f"{row['exit']} | {row['disposition']} |")
    print()
    print("| cvc5 proof granularity | Solver | Trust commands | Logos |")
    print("|---|---|---:|---|")
    for name, row in evidence["cpc"]["certificates"].items():
        print(f"| `{name}` | {row['solver']} | {row['trust_commands']} | {row['logos']} |")


if __name__ == "__main__":
    main()
