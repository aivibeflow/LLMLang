"""Plot storage and load measurements from a comparison ledger."""

import argparse
import json
from pathlib import Path
from statistics import median

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    profiles = evidence["profiles"]
    names = [profile["profile"] for profile in profiles]
    centers = range(len(profiles))
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.7), constrained_layout=True)

    def bars(axis, left, right, left_label, right_label, errors=None):
        axis.bar([i - 0.19 for i in centers], left, width=0.36, color="#1f658e",
                 label=left_label, yerr=None if errors is None else errors[0], capsize=3)
        axis.bar([i + 0.19 for i in centers], right, width=0.36, color="#b55332",
                 label=right_label, yerr=None if errors is None else errors[1], capsize=3)
        axis.set_xticks(list(centers), names, rotation=23, ha="right")
        axis.set_axisbelow(True)
        axis.grid(axis="y", alpha=0.25)
        axis.legend()

    checkout = [p["baseline_bytes"] / 2**20 for p in profiles]
    bars(axes[0], checkout,
         [p["history"][-1]["pack_bytes"] / 2**20 for p in profiles],
         "Baseline checkout", "Git pack + index, 5 commits")
    axes[0].set_ylim(top=axes[0].get_ylim()[1] * 1.18)
    axes[0].set_title("Physical storage")
    axes[0].set_ylabel("MiB")
    loads = [
        [[r["ms"] for r in profile["cache_loads"]
          if r["cache_percent"] == cache]
         for profile in profiles]
        for cache in (0, 99)
    ]
    medians = [[median(samples) for samples in layout] for layout in loads]
    errors = [
        [[abs(mid - bound(samples)) for mid, samples in zip(values, layout)]
         for bound in (min, max)]
        for values, layout in zip(medians, loads)
    ]
    bars(axes[1], *medians, "Empty cache", "99% cache hits", errors=errors)
    axes[1].set_title("Validated load, one process")
    axes[1].set_ylabel("Wall time, ms (median and range)")
    figure.suptitle(f'RT-27 · {evidence["objects"]:,} synthetic SPG records · one indexed container')
    figure.savefig(args.out, dpi=160)


if __name__ == "__main__":
    main()
