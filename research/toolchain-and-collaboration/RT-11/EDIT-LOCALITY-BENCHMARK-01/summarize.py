#!/usr/bin/env python3
"""Summarize the paired samples and render a reproducible comparison."""

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
from statistics import median

SCOPES = ("local", "shared", "broad")
ROUTES = ("full", "incremental")


def collect(directory):
    sample = directory / "samples.csv"
    with sample.open(newline="") as source:
        data = list(csv.DictReader(source))
    profile = json.loads((directory / "profile.json").read_text())
    grouped = {}
    for row in data:
        case, block, route = row["scenario"], int(row["block"]), row["route"]
        routes = grouped.setdefault((case, block), {})
        if route in routes:
            raise AssertionError(f"Duplicate result: {case}, {block}, {route}")
        routes[route] = row
    comparisons = {}
    blocks = profile["blocks"]
    if len(grouped) != blocks * len(SCOPES):
        raise AssertionError("Unexpected paired block count")
    for case in SCOPES:
        paired = [grouped[case, block] for block in range(blocks)]
        if any(set(pair) != set(ROUTES) or
               len({entry["artifact_sha256"] for entry in pair.values()}) != 1 or
               len({entry["observed"] for entry in pair.values()}) != 1 for pair in paired):
            raise AssertionError(f"Paired artifact mismatch: {case}")
        records = {}
        for route in ROUTES:
            rows = [pair[route] for pair in paired]
            work = {(int(row["compiles"]), int(row["links"])) for row in rows}
            if len(work) != 1:
                raise AssertionError("Inconsistent action counts within an edit scope")
            compiles, links = next(iter(work))
            wall_ms = [int(row["wall_ns"]) / 1_000_000 for row in rows]
            records[route] = {
                "compiles": compiles, "links": links, "wall_ms_median": round(median(wall_ms), 6),
                "wall_ms_min": round(min(wall_ms), 6), "wall_ms_max": round(max(wall_ms), 6),
                "child_cpu_ms_median": round(median(int(row["child_cpu_ns"])
                                                    for row in rows) / 1_000_000, 6),
            }
        ratios = [int(pair["full"]["wall_ns"]) / int(pair["incremental"]["wall_ns"])
                  for pair in paired]
        comparisons[case] = {
            **records, "output": int(paired[0]["full"]["observed"]),
            "paired_binary_matches": len(paired),
            "full_over_incremental_wall_median": round(median(ratios), 6),
            "full_over_incremental_wall_min": round(min(ratios), 6),
            "full_over_incremental_wall_max": round(max(ratios), 6),
        }
    return {"schema": "llmlang-native-edit-locality/1", "profile": profile,
            "samples_sha256": sha256(sample.read_bytes()).hexdigest(),
            "paired_comparisons": len(grouped), "scopes": comparisons}


def plot(summary, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.hashsalt": "llmlang-native-edit-locality",
                         "svg.fonttype": "none", "text.color": "#192843",
                         "axes.labelcolor": "#192843", "xtick.color": "#192843",
                         "ytick.color": "#192843"})
    combos = summary["scopes"]
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.7), constrained_layout=True)
    labels = ("Local file", "Shared header", "Common header")
    width = 0.32
    for i, (route, label, color) in enumerate((("full", "Full rebuild", "#436688"),
                                               ("incremental", "Exact incremental", "#008474"))):
        xs = [j + width * (i - 0.5) for j in range(3)]
        actions = [combos[key][route]["compiles"] for key in SCOPES]
        medians = [combos[key][route]["wall_ms_median"] for key in SCOPES]
        errors = [[medians[j] - combos[key][route]["wall_ms_min"] for j, key in enumerate(SCOPES)],
                  [combos[key][route]["wall_ms_max"] - medians[j] for j, key in enumerate(SCOPES)]]
        axes[0].bar(xs, actions, width=width, label=label, color=color, zorder=2)
        axes[1].bar(xs, medians, width=width, color=color, yerr=errors, capsize=3, zorder=2)
    axes[0].set_ylabel("Translation units compiled")
    axes[1].set_ylabel("Elapsed time (ms)")
    fig.legend(loc="outside upper center", ncols=2, frameon=False)
    for ax in axes:
        ax.set_xticks(range(3), labels)
        ax.grid(axis="y", color="#dee5ec", linewidth=0.75)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylim(0, 21)
    fig.savefig(path, format="svg", metadata={"Date": None, "Creator": "LLMLang RT-11"})
    plt.close(fig)
    path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--plot", type=Path)
    args = parser.parse_args()
    summary = collect(args.directory)
    if args.plot:
        plot(summary, args.plot)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
