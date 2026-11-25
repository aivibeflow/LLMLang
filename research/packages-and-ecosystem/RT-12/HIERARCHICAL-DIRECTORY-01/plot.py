"""Draw the measured directory read calls and byte volumes for larger profiles."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


LAYOUTS = {
    "omitted": ("#5d6773", "s", "Canonical headers or retained flat"),
    "flat-seek": ("#b95d29", "o", "Flat per-row seeks"),
    "two-level": ("#197081", "D", "Two-level directory"),
}
WORKLOADS = {
    "single": "Single lookup",
    "dispersed-64": "64 dispersed lookups",
    "clustered-64": "64 clustered lookups",
}


def draw(evidence, output):
    plt.rcParams.update({"svg.hashsalt": "rt12-hierarchical-directory", "font.size": 9})
    fig, axes = plt.subplots(2, 3, figsize=(10, 5.8), sharex=True, sharey=True, layout="constrained")
    for row, scale in enumerate(evidence["scales"][-2:]):
        for column, (query, title) in enumerate(WORKLOADS.items()):
            panel = axes[row, column]
            modes = scale["queries"][query]["modes"]
            for mode, (color, marker, _) in LAYOUTS.items():
                reading = modes[mode]
                panel.scatter(reading["read_calls"], reading["read_bytes"] / 1024,
                              marker=marker, color=color, s=54, zorder=3)
            panel.grid(alpha=0.22, which="major")
            panel.set_xscale("log")
            panel.set_yscale("log")
            panel.set_title(f"{title} · {scale['blocks']:,} blocks", fontsize=9)
            if row == 1:
                panel.set_xlabel("Read calls")
            if column == 0:
                panel.set_ylabel("Directory reads (KiB)")
    fig.suptitle("Sparse directory lookup costs", fontsize=14, fontweight="bold")
    handles = [Line2D([], [], marker=marker, linestyle="None", color=color, label=label)
               for color, marker, label in LAYOUTS.values()]
    fig.legend(handles=handles, loc="outside lower center", ncol=3, frameon=False)
    fig.savefig(output, metadata={"Date": None})
    plt.close(fig)
    if output.suffix == ".svg":
        contents = output.read_text(encoding="utf-8")
        output.write_text("\n".join(line.rstrip() for line in contents.splitlines()) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    draw(json.loads(args.evidence.read_text()), args.output)
