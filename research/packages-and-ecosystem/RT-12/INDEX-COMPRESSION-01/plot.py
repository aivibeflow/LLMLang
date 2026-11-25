"""Plot the archive size and lookup read volume from the exact evidence receipt."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


COLORS = {"raw": "#637083", "gzip": "#247286", "bzip2": "#b35633"}


def plot(evidence, output):
    rows = list(evidence["layouts"].items())
    positions = list(range(len(rows)))
    labels = [name.replace("-block-", " / ").replace("-whole", " / whole") for name, _ in rows]
    colors = [COLORS[name.split("-", 1)[0]] for name, _ in rows]
    archive_sizes = [row["artifact_bytes"] / 1024 for _, row in rows]
    lookup_sizes = [row["operations"]["lookup-fresh"]["read_bytes"] / 1024 for _, row in rows]
    plt.rcParams.update({"svg.hashsalt": "rt12-index-compression", "font.size": 10})
    fig, (left, right) = plt.subplots(1, 2, figsize=(10, 5.2), sharey=True, layout="constrained")

    left.barh(positions, archive_sizes, color=colors, height=0.68)
    left.set_yticks(positions, labels)
    left.invert_yaxis()
    left.set_xlabel("Archive size (KiB)")
    left.set_xlim(0, 565)
    for position, value in zip(positions, archive_sizes, strict=True):
        left.text(value + 5, position, f"{value:.0f}", va="center", fontsize=9)

    for position, size, (_, row), color in zip(positions, lookup_sizes, rows, colors, strict=True):
        right.scatter(size, position, s=44, color=color, zorder=2)
        retained = row["operations"].get("lookup-retained")
        if retained:
            right.scatter(retained["read_bytes"] / 1024, position, marker="D", s=39,
                          facecolors="white", edgecolors=color, zorder=3)
    right.set_xscale("log")
    right.set_xlim(35, 25_000)
    right.set_xlabel("Bytes returned by file reads across 64 queries (KiB)")
    right.grid(axis="x", which="major", alpha=0.25)
    right.set_axisbelow(True)
    fig.suptitle("Package index size and point-lookup reads", fontsize=15, fontweight="bold")
    left.legend(handles=[Patch(color=color, label=name) for name, color in COLORS.items()],
                loc="lower center", bbox_to_anchor=(0.5, -0.22), ncol=3, frameon=False)
    right.legend(handles=[
        Line2D([], [], marker="o", color="#344153", linestyle="None", label="No retained decoded rows"),
        Line2D([], [], marker="D", color="#344153", markerfacecolor="white",
               linestyle="None", label="Retain whole decoded index"),
    ], loc="lower center", bbox_to_anchor=(0.5, -0.25), frameon=False)
    fig.savefig(output, metadata={"Date": None})
    plt.close(fig)
    if output.suffix == ".svg":
        rendered = output.read_text(encoding="utf-8")
        output.write_text("\n".join(line.rstrip() for line in rendered.splitlines()) + "\n",
                          encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    plot(json.loads(args.evidence.read_text()), args.output)


if __name__ == "__main__":
    main()
