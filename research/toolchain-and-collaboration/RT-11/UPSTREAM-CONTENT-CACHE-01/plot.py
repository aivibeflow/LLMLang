#!/usr/bin/env python3
"""Plot paired speedups for the whole-project cache against both native baselines."""

import argparse
import json
from pathlib import Path
from statistics import median

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECTS = {"memchr": "Rust · memchr", "pflag": "Go · pflag", "fmt": "C++ · fmt"}
STAGES = {"cold": "Cold", "warm": "Warm", "edited": "Edited", "reverted": "Reverted"}
BASELINES = {"clean": ("Fresh", "#315f93"), "incremental": ("Incremental", "#b85723")}


def plot(data, output):
    figure, axes = plt.subplots(1, 3, sharey=True, figsize=(10, 3.5), layout="constrained")
    print("| Project | Stage | Cache hits | Cache median (ms) | Fresh / cache median [min, max] | Incremental / cache median [min, max] |")
    print("| --- | --- | ---: | ---: | ---: | ---: |")
    for axis, (name, project) in zip(axes, data["projects"].items()):
        for y, (stage, label) in enumerate(STAGES.items()):
            results = [trial[stage]["measurements"] for trial in project["trials"]]
            contents = [row["content"] for row in results]
            ratios = []
            for index, (baseline, (baseline_label, color)) in enumerate(BASELINES.items()):
                position = y + (index * 2 - 1) * 0.14
                values = [row[baseline]["wall_ns"] / row["content"]["wall_ns"] for row in results]
                center = median(values)
                ratios.append(f"{center:.3f} [{min(values):.3f}, {max(values):.3f}]")
                axis.hlines(position, min(values), max(values), color=color, alpha=0.75, linewidth=1.6)
                axis.scatter(values, [position] * len(values), color=color, alpha=0.45, s=22)
                legend = baseline_label if name == "memchr" and y == 0 else None
                axis.scatter(center, position, color=color, edgecolor="white", linewidth=0.6,
                             s=54, zorder=4, label=legend)
            elapsed = median(row["wall_ns"] / 1e6 for row in contents)
            hits = sum(row["cache_hit"] for row in contents)
            print(f"| {name} | {label} | {hits}/{len(contents)} | {elapsed:.3f} | {' | '.join(ratios)} |")
        axis.set_xscale("log")
        axis.set_title(PROJECTS[name])
        axis.axvline(1, linewidth=1, color="#535353", linestyle="--")
        axis.set_yticks(range(len(STAGES)), STAGES.values())
        axis.grid(axis="x", color="#d9d9d9", alpha=0.75)
        axis.spines[["top", "right"]].set_visible(False)
    axes[0].invert_yaxis()
    axes[0].legend(loc="lower right", fontsize=8, frameon=False)
    figure.supxlabel("Baseline / cache elapsed time (logarithmic scale)")
    metadata = {"Date": None} if output.suffix == ".svg" else None
    figure.savefig(output, metadata=metadata)
    if output.suffix == ".svg":
        output.write_text("\n".join(line.rstrip() for line in output.read_text().splitlines()) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with matplotlib.rc_context({"svg.hashsalt": "llmlang-upstream-content-cache", "svg.fonttype": "none"}):
        plot(json.loads(args.input.read_text()), args.output)
