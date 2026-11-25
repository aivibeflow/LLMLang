#!/usr/bin/env python3
"""Plot the measured phases and print median time by workload."""

import argparse
import json
from pathlib import Path
from statistics import median

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PHASES = {
    "discovery": "Dependency discovery",
    "hashing": "Read and hash inputs",
    "scheduling": "Topological scheduling",
    "storage": "Verify and restore payloads",
    "verification": "Run and decode checks",
}
COLORS = ("#207572", "#3159a5", "#ba591c")


def plot(ledger, output):
    workloads = ledger["workloads"]
    fig, axis = plt.subplots(figsize=(9, 4.2), layout="constrained")
    for index, (workload, color) in enumerate(zip(workloads, COLORS)):
        offset = (index - 1) * 0.20
        for row, phase in enumerate(PHASES):
            values = [sample["phase_ns"][phase] / 1e6 for sample in workload["samples"]]
            center = row + offset
            axis.hlines(center, min(values), max(values), color=color, alpha=0.58, linewidth=1.8)
            axis.scatter(values, [center] * len(values), color=color, alpha=0.36, s=17, zorder=3)
            label = f"{workload['components']} components" if row == 0 else None
            axis.scatter(median(values), center, color=color, edgecolors="white", linewidths=0.65,
                         s=47, zorder=4, label=label)
    axis.set_xscale("log")
    axis.set_yticks(range(len(PHASES)), PHASES.values())
    axis.invert_yaxis()
    axis.set_xlabel("Elapsed time per phase (ms, logarithmic scale)")
    axis.grid(axis="x", which="major", color="#d0d5dd", alpha=0.6)
    axis.legend(loc="upper center", bbox_to_anchor=(0.5, 1.14), ncols=3, frameon=False)
    axis.spines[["top", "right"]].set_visible(False)
    metadata = {"Date": None} if output.suffix == ".svg" else None
    fig.savefig(output, metadata=metadata)
    if output.suffix == ".svg":
        lines = output.read_text().splitlines()
        output.write_text("\n".join(line.rstrip() for line in lines) + "\n")

    counts = " | ".join(str(workload["components"]) for workload in workloads)
    print(f"| Median phase time (ms) | {counts} |")
    print("| --- | ---: | ---: | ---: |")
    for phase, label in PHASES.items():
        times = [median(sample["phase_ns"][phase] / 1e6 for sample in workload["samples"])
                 for workload in workloads]
        print(f"| {label} | " + " | ".join(f"{value:.3f}" for value in times) + " |")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with matplotlib.rc_context({"svg.hashsalt": "llmlang-build-phase-overhead", "svg.fonttype": "none"}):
        plot(json.loads(args.input.read_text()), args.output)
