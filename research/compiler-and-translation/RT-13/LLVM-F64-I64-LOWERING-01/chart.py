"""Render the LLVM refinement and execution comparison from its evidence ledger."""

import json
from pathlib import Path

LABELS = {
    "bits_branch": "Bit guard and branch",
    "ordered_branch": "Ordered comparisons and branch",
    "ordered_select": "Ordered comparisons and masked value",
    "guarded_saturate": "Guarded saturation",
    "saturate": "Plain saturation",
    "inclusive_upper": "Inclusive upper-bound control",
    "unmasked_value": "Unmasked conversion control",
}


def main():
    data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
    print("| LLVM route | Original Alive2 result | Optimized Alive2 results | Native mismatches per configuration | Vellvm assertions per extraction |")
    print("|---|---|---|---:|---:|")
    for route, label in LABELS.items():
        result = data["original_refinement"].get(route, {"verdict": "reference"})
        verdict = result["verdict"]
        if "input" in result:
            verdict += f" at `{result['input']}`"
        optimized = [profile["verdicts"][route]["verdict"]
                     for profile in data["optimized_refinement"].values() if route in profile["verdicts"]]
        native = data["native_mismatches"].get(route, "—")
        replay = data["vellvm"][route]["per_extraction"]
        checked = replay["passed"] + replay["failed"]
        print(f"| {label} | {verdict} | {', '.join(optimized) or '—'} | {native} | {replay['passed']}/{checked} |")


if __name__ == "__main__":
    main()
