"""Plot the medians and observed ranges of the RT-25 replay ledger."""

import argparse
import json
from pathlib import Path
from statistics import median

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


METRICS = (
    ("build_ns", "Graph construction", "ms", 1_000_000),
    ("impact_ns", "Traversal and serialization", "ms", 1_000_000),
    ("live_kib", "Live graph RSS", "MiB", 1024),
    ("peak_kib", "Process peak RSS", "MiB", 1024),
    ("after_drop_kib", "RSS 50 ms after drop", "MiB", 1024),
)
LABELS = {"glibc": "glibc", "jemalloc": "jemalloc", "tcmalloc": "TCMalloc minimal", "mimalloc": "mimalloc"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    ledger = json.loads(args.ledger.read_text())
    names = list(ledger["providers"])

    matplotlib.rcParams.update({"svg.fonttype": "none", "svg.hashsalt": "llmlang-rt25-replay"})
    figure, axes = plt.subplots(2, 3, figsize=(11.5, 6), layout="constrained")
    for axis, (field, label, unit, scale) in zip(axes.flat, METRICS):
        for y, name in enumerate(names):
            data = [sample[field] / scale for sample in ledger["samples"] if sample["provider"] == name]
            middle = median(data)
            axis.errorbar(middle, y,
                          xerr=[[middle - min(data)], [max(data) - middle]],
                          fmt="o", color="#136180", capsize=3, markersize=4)
        axis.set_yticks(range(len(names)), [LABELS[name] for name in names])
        axis.invert_yaxis()
        axis.set_title(label, loc="left", fontweight="semibold")
        axis.set_xlabel(unit)
        axis.grid(axis="x", linewidth=0.5, alpha=0.5)
    axes.flat[-1].axis("off")
    axes.flat[-1].text(0.02, 0.62,
                       f"Points show medians of {ledger['sample_count_per_provider']} runs.\n"
                       "Lines show observed ranges.\n"
                       "Each metric has its own scale.",
                       transform=axes.flat[-1].transAxes, linespacing=1.6, fontsize=10)
    figure.suptitle("RT-25 synthetic dependency graph under four process allocators", fontsize=15)
    figure.savefig(args.output, metadata={"Date": None})
    if args.output.suffix == ".svg":
        svg = args.output.read_text(encoding="utf-8")
        args.output.write_text("\n".join(line.rstrip() for line in svg.splitlines()) + "\n",
                               encoding="utf-8")


if __name__ == "__main__":
    main()
