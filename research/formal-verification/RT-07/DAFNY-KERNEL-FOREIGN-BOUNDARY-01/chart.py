"""Render Dafny proof outcomes and native ABI disagreements."""

import json
from pathlib import Path

PROOFS = {
    "default_warning_gate": "Default warning policy",
    "warnings_visible": "Warnings allowed and visible",
    "explicit_external_contracts": "External contracts explicitly allowed",
    "local_dropped_guard": "Local implementation drops overflow check",
}
ROUTES = {
    "c_checked": "Checked C provider and unsigned bridge",
    "c_wrapping": "Wrapping C provider",
    "c_overflow_first": "C checks overflow before ordinal",
    "abi_signed_result": "Checked C provider and signed bridge",
}


def main():
    data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
    print("| Dafny verification profile | Verified units | Errors | Exit code | Foreign contract warning |")
    print("|---|---:|---:|---:|---|")
    for profile, label in PROOFS.items():
        result = data["proofs"]["4.12.1"][profile]
        warning = "shown" if result["foreign_assumption_warning"] else "absent"
        print(f"| {label} | {result['verified']} | {result['errors']} | {result['exit']} | {warning} |")
    print()
    print("| Native route through the generated Dafny caller | Mismatches per configuration |")
    print("|---|---:|")
    mismatches = data["native_mismatches_per_profile"]
    for route, label in ROUTES.items():
        print(f"| {label} | {mismatches[route]} |")


if __name__ == "__main__":
    main()
