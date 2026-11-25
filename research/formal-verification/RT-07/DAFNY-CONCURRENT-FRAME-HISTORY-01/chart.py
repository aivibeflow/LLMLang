"""Render native history counts and Dafny frame-check results."""

import json
from pathlib import Path

LABELS = {
    "SharedRead": "Function reads a shared cell",
    "DefaultReadFrame": "Concurrent method omits its read frame",
    "DistinctButShared": "Method writes a cell distinct from another argument",
    "AssumedFunctionRead": "Function annotates its nonempty read frame",
}


def main():
    data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
    print("| Dafny control | Rejected frame |")
    print("|---|---|")
    for name, frame in data["proofs"]["4.12.1"]["diagnostics"].items():
        print(f"| {LABELS[name]} | `{frame}` |")
    print()
    print("| Native route | Participants | Histories | Linearizable | Wrong final count |")
    print("|---|---:|---:|---:|---:|")
    for route, label in (("split", "Separate atomic load/store"), ("rmw", "Atomic fetch-add")):
        for actors, result in data["metrics_per_profile"][route].items():
            print(f"| {label} | {actors} | {result['histories']} | {result['linearizable']} | "
                  f"{result['wrong_final_count']} |")


if __name__ == "__main__":
    main()
