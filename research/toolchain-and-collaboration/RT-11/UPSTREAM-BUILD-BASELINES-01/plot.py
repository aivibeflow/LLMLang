#!/usr/bin/env python3
"""Visualize paired clean and incremental upstream build times."""

import argparse
import json
from pathlib import Path
from statistics import median

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECTS = {"memchr": "Rust · memchr", "pflag": "Go · pflag", "fmt": "C++ · fmt"}
STAGES = {"cold": "Cold", "warm": "Warm", "edited": "Library edit"}
METHODS = {"clean": ("Clean", "#315f93"), "incremental": ("Incremental", "#b85723")}


def plot(ledger, output):
    figure, axes = plt.subplots(1, 3, sharey=True, figsize=(10, 3.5), layout="constrained")
    print("| Project | Stage | Clean median (ms) | Incremental median (ms) | Paired clean / incremental | Exact byte matches |")
    print("| --- | --- | ---: | ---: | ---: | ---: |")
    for axis, (name, project) in zip(axes, ledger["projects"].items()):
        for y, (stage, label) in enumerate(STAGES.items()):
            observations = [trial["stages"][y] for trial in project["trials"]]
            results = [observation["measurements"] for observation in observations]
            ratios = [row["clean"]["elapsed_ns"] / row["incremental"]["elapsed_ns"] for row in results]
            matching = sum(observation["binary_bytes_agree"] for observation in observations)
            medians = []
            for index, (method, (method_label, color)) in enumerate(METHODS.items()):
                position = y + (index * 2 - 1) * 0.13
                values = [row[method]["elapsed_ns"] / 1e6 for row in results]
                medians.append(median(values))
                axis.hlines(position, min(values), max(values), color=color, linewidth=1.8)
                axis.scatter(values, [position] * len(values), color=color, alpha=0.4, s=18)
                legend_label = method_label if y == 0 and name == "memchr" else None
                axis.scatter(medians[-1], position, color=color, edgecolor="white",
                             linewidth=0.6, s=51, zorder=4, label=legend_label)
            print(f"| {name} | {label} | {medians[0]:.2f} | {medians[1]:.2f} | "
                  f"{median(ratios):.2f} [{min(ratios):.2f}, {max(ratios):.2f}] | {matching}/{len(ratios)} |")
        axis.set_xscale("log")
        axis.set_title(PROJECTS[name])
        axis.set_yticks(range(len(STAGES)), STAGES.values())
        axis.grid(axis="x", color="#d9d9d9", alpha=0.75)
        axis.spines[["top", "right"]].set_visible(False)
    axes[0].invert_yaxis()
    axes[0].legend(loc="lower right", frameon=False, fontsize=8)
    figure.supxlabel("Elapsed build time (ms, logarithmic scale)")
    metadata = {"Date": None} if output.suffix == ".svg" else None
    figure.savefig(output, metadata=metadata)
    if output.suffix == ".svg":
        output.write_text("\n".join(line.rstrip() for line in output.read_text().splitlines()) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with matplotlib.rc_context({"svg.hashsalt": "llmlang-upstream-build-baselines", "svg.fonttype": "none"}):
        plot(json.loads(args.input.read_text()), args.output)
