"""Render the archived concurrent allocator timings and resident-memory observations."""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt


def draw(ledger, output):
    providers = ("glibc", "jemalloc", "mimalloc", "gperftools", "google")
    labels = ("glibc", "jemalloc", "mimalloc", "gperftools", "Google\nTCMalloc")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
    for producers, offset, color in ((1, -0.14, "#276486"), (4, 0.14, "#a54922")):
        groups = [ledger["summary"][f"{provider}/{producers}"] for provider in providers]
        positions = [index + offset for index in range(len(groups))]
        times = [group["elapsed_ns"] for group in groups]
        scale = 1024 * producers * 1000
        middle = [row["median"] / scale for row in times]
        errors = [[(row["median"] - row["p10"]) / scale for row in times],
                  [(row["p90"] - row["median"]) / scale for row in times]]
        label = f"{producers} producer" if producers == 1 else "4 producers"
        axes[0].errorbar(positions, middle, yerr=errors, fmt="o", color=color, capsize=3, label=label)
        peaks = [group["peak_kib"]["median"] / 1024 for group in groups]
        settled = [group["after_drop_kib"]["median"] / 1024 for group in groups]
        axes[1].scatter(positions, peaks, color=color, marker="o")
        axes[1].scatter(positions, settled, facecolors="none", edgecolors=color, marker="s")
    axes[0].set(ylabel="Wall time per packet (µs)", title="Median and empirical p10–p90")
    axes[1].set(ylabel="Process resident memory (MiB)", title="Median early HWM (●) and later RSS (□)")
    for axis in axes:
        axis.set_xticks(range(len(labels)), labels)
        axis.grid(axis="y", alpha=0.25)
    axes[0].legend(frameon=False)
    fig.savefig(output, dpi=150, metadata={"Software": "Matplotlib 3.10.8"})
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    draw(json.loads(args.ledger.read_text()), args.output)
