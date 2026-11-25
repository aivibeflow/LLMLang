"""Plot all measured build runs, with a median marker for each group."""

import argparse
import json
from pathlib import Path
from statistics import median

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

STAGES = ("cold", "warm", "local", "component", "broad")
METHODS = (
    ("clean", "Forced rebuild", "#555555", "s", -.23),
    ("incremental", "Incremental Make", "#0072B2", "o", 0),
    ("content", "Content-keyed", "#D55E00", "^", .23),
)


def plot(source, output):
    data = json.loads(source.read_bytes())
    plt.rcParams.update({"svg.hashsalt": "rt11-compile-cache-timing", "svg.fonttype": "none",
                         "font.size": 10, "figure.dpi": 120})
    fig, ax = plt.subplots(figsize=(8.0, 4.3), layout="constrained")
    for method, label, color, marker, offset in METHODS:
        for position, stage in enumerate(STAGES):
            times = [row["elapsed_ns"] / 1e6 for row in data["samples"]
                     if row["stage"] == stage and row["method"] == method]
            y = position + offset
            ax.plot([min(times), max(times)], [y, y], color=color, alpha=.45)
            ax.scatter(times, [y] * len(times), s=15, color=color, alpha=.4, marker=marker)
            ax.scatter([median(times)], [y], s=48, color=color, marker=marker,
                       label=label if position == 0 else None)
    ax.set_xscale("log")
    ax.set_xlabel("Elapsed time (milliseconds, logarithmic scale)")
    ax.set_yticks(range(len(STAGES)), ("Cold", "Warm", "Local edit", "Component edit", "Broad edit"))
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=.22, which="both")
    ax.set_title(f"Synthetic twelve-unit C++ build ({data['repetitions']} runs per cell)")
    ax.legend(loc="upper center", bbox_to_anchor=(.5, -.13), ncols=3, frameon=False)
    fig.savefig(output, metadata={"Date": None})
    plt.close(fig)
    if output.suffix == ".svg":
        svg = output.read_text(encoding="utf-8")
        output.write_text("\n".join(line.rstrip() for line in svg.splitlines()) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plot(args.input, args.output)
