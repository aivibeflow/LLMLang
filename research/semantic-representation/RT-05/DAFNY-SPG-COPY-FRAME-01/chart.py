"""Render final-state and access-trace differences from the copy ledger."""

import json
from pathlib import Path

LABELS = {
    "SnapshotCopy": "Snapshot copy",
    "DirectedCopy": "Directional copy",
    "ForwardOnly": "Forward copy without applying its precondition",
    "SnapshotWithWrite": "Snapshot with an extra write under coarse frame",
}


def main():
    data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
    print("| Generated route | Final arrays different from specification | Accesses outside declared spans | Traces different from snapshot |")
    print("|---|---:|---:|---:|")
    for method, label in LABELS.items():
        measure = data["metrics"][method]
        print(f"| {label} | {measure['result_mismatches']:,} | {measure['outside_spans']:,} | "
              f"{measure['trace_differences']:,} |")


if __name__ == "__main__":
    main()
