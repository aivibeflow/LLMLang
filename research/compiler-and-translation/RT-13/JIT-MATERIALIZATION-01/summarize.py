"""Summarize archived JIT timings and reproduce the comparison figure."""

import argparse
from collections import defaultdict
import csv
import json
from math import floor
from pathlib import Path


PROFILES = ("llvm-O0", "llvm-O3", "cranelift-none", "cranelift-speed")


def quantile(sorted_ns, fraction):
    position = fraction * (len(sorted_ns) - 1)
    lower = floor(position)
    upper = min(lower + 1, len(sorted_ns) - 1)
    return (sorted_ns[lower] + (position - lower) * (sorted_ns[upper] - sorted_ns[lower])) / 1000


def summarize(paths):
    rows = defaultdict(list)
    seeds = set()
    for path in paths:
        with path.open(encoding="utf-8", newline="") as stream:
            for datum in csv.DictReader(stream):
                phase = "first" if datum["sample"] == "0" else "subsequent"
                profile, time, seed = datum["profile"], int(datum["elapsed_ns"]), datum["seed"]
                if profile not in PROFILES or time <= 0:
                    raise ValueError(f"Invalid sample: {datum}")
                seeds.add(seed)
                for group in (seed, "combined"):
                    rows[group, profile, phase].append(time)

    summary = {}
    for group in ["combined", *sorted(seeds)]:
        summary[group] = {}
        for profile in PROFILES:
            summary[group][profile] = {}
            for phase in ("first", "subsequent"):
                times = sorted(rows[group, profile, phase])
                summary[group][profile][phase] = {
                    "n": len(times), **{f"p{p}_us": round(quantile(times, p / 100), 1) for p in (10, 50, 90)},
                }
    return summary


def chart(combined, destination):
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.3), sharex=True, sharey=True, layout="constrained")
    labels = ("LLVM ORC O0", "LLVM ORC O3", "Cranelift none", "Cranelift speed")
    colors = ("#26547c", "#26547c", "#9a3412", "#9a3412")
    for axis, phase, heading in zip(axes, ("first", "subsequent"), ("First in each process", "Subsequent modules")):
        for index, (name, color) in enumerate(zip(PROFILES, colors)):
            record = combined[name][phase]
            axis.hlines(index, record["p10_us"], record["p90_us"], color=color, linewidth=2.2)
            axis.scatter(record["p50_us"], index, color=color, s=32, zorder=2)
        axis.set_xscale("log")
        axis.set_yticks(range(len(labels)), labels=labels)
        axis.set_title(heading)
        axis.set_xlabel("Ready-to-call time (µs, log scale)")
        axis.grid(True, axis="x", color="#dce2e6")
    axes[0].invert_yaxis()
    fig.suptitle("Checked addition on x86-64 · median and 10th–90th percentiles")
    fig.savefig(destination, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("samples", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--figure", type=Path)
    args = parser.parse_args()
    summary = summarize(args.samples)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    if args.figure:
        chart(summary["combined"], args.figure)
