"""Plot sampled dispatch timing intervals for the archived native trials."""

import argparse
from collections import defaultdict
import csv
from pathlib import Path
from statistics import median

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROUTES = ("native-runtime", "c", "cpp", "rust", "go")
LABELS = ("Direct C runtime", "C adapter", "C++ adapter", "Rust adapter", "Go cgo adapter")


def points(samples):
    grouped = defaultdict(list)
    with samples.open(newline="") as source:
        for trial in csv.DictReader(source):
            key = trial["workload"], trial["adapter"]
            grouped[key].append(int(trial["elapsed_ns"]) / int(trial["calls"]))
    return grouped


def draw(samples, output):
    grouped = points(samples)
    plt.rcParams.update({"svg.hashsalt": "rt13-dispatch-timing", "font.size": 10})
    fig, grid = plt.subplots(1, 2, figsize=(10, 4.4), sharey=True, layout="constrained")
    for ax, (workload, title, color) in zip(grid, (
        ("all-success", "All calls commit", "#267589"),
        ("mixed-status", "Mixed success and refusal", "#b55b35"),
    ), strict=True):
        for row, route in enumerate(ROUTES):
            values = grouped[workload, route]
            middle = median(values)
            ax.errorbar(middle, row, xerr=[[middle - min(values)], [max(values) - middle]],
                        color=color, capsize=4, fmt="o")
            ax.annotate(f"{middle:.2f}", (middle, row), xytext=(5, 7),
                        textcoords="offset points", fontsize=9)
        ax.set_xscale("log")
        ax.set_xlim(1, 200)
        ax.set_title(title)
        ax.set_xlabel("Nanoseconds per call (log scale)")
        ax.grid(axis="x", which="major", alpha=0.24)
    grid[0].set_yticks(range(len(ROUTES)), LABELS)
    grid[0].set_ylim(len(ROUTES) - 0.5, -0.5)
    fig.suptitle("Native dispatch latency by ABI route\nMedian and min–max across seven trials",
                 fontsize=14, fontweight="bold")
    fig.savefig(output, metadata={"Date": None})
    plt.close(fig)
    if output.suffix == ".svg":
        raw = output.read_text(encoding="utf-8")
        output.write_text("\n".join(line.rstrip() for line in raw.splitlines()) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("samples", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    draw(args.samples, args.output)
