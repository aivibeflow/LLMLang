#!/usr/bin/env python3
"""Plot block-paired build speedup ratios against the two baselines."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SCENARIOS = {"cold": "Cold", "warm": "Warm", "local": "Local edit",
             "component": "Component edit", "broad": "Broad edit"}
BASELINES = {"clean": "Forced rebuild", "incremental": "Incremental Make"}


def plot(data, output):
    fig, axes = plt.subplots(1, 2, sharey=True, figsize=(9, 3.8), layout="constrained")
    for baseline, axis in zip(BASELINES, axes):
        statistics = []
        for index, (stage, record) in enumerate(data["paired"].items()):
            summary = record["comparisons"][baseline]
            ratios = [row[f"speedup_vs_{baseline}"] for row in record["pairs"]]
            statistics.append((stage, summary))
            axis.hlines(index, summary["min"], summary["max"], color="#34618d", linewidth=2)
            axis.scatter(ratios, [index] * len(ratios), color="#34618d", s=22, alpha=0.46, zorder=3)
            axis.scatter(summary["median"], index, color="#14416c", edgecolor="white", linewidth=0.7,
                         s=55, zorder=4)
        axis.axvline(1, linewidth=1, linestyle="--", color="#4c4c4c")
        axis.grid(axis="x", color="#d9d9d9", alpha=0.8)
        axis.set_xscale("log" if baseline == "clean" else "linear")
        suffix = "log scale" if baseline == "clean" else "linear scale"
        axis.set_xlabel(f"Baseline / cache elapsed time ({suffix})")
        axis.set_title(BASELINES[baseline])
        axis.set_yticks(range(len(statistics)), [SCENARIOS[stage] for stage, _ in statistics])
        axis.spines[["top", "right"]].set_visible(False)
    axes[0].invert_yaxis()
    metadata = {"Date": None} if output.suffix == ".svg" else None
    fig.savefig(output, metadata=metadata)
    if output.suffix == ".svg":
        lines = output.read_text().splitlines()
        output.write_text("\n".join(line.rstrip() for line in lines) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with matplotlib.rc_context({"svg.hashsalt": "llmlang-paired-cache-speedup", "svg.fonttype": "none"}):
        plot(json.loads(args.input.read_text()), args.output)
