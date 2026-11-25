"""Render medians and p10–p90 from the checked allocator trials."""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent
COLUMNS = (
    (("build_ns", "Graph build"), ("impact_ns", "Traversal and serialization")),
    (("live_kib", "Live graph"), ("peak_kib", "Process peak"), ("after_drop_kib", "50 ms after drop")),
)


def chart(source, output):
    data = json.loads(source.read_text())["summary"]
    figure, axes = plt.subplots(1, 2, figsize=(9.2, 3.5), layout="constrained")
    for axis, fields, divisor, label in zip(axes, COLUMNS, (1e6, 1024), ("Milliseconds", "MiB"), strict=True):
        for provider, title, color, delta in (("glibc", "glibc", "#176183", -0.16),
                ("modern-google-tcmalloc", "Google TCMalloc", "#954f2b", 0.16)):
            for index, (field, _) in enumerate(fields):
                point = data[provider][field]
                central = point["median"] / divisor
                bounds = [[central - point["p10"] / divisor], [point["p90"] / divisor - central]]
                axis.errorbar(central, index + delta, xerr=bounds, fmt="o", capsize=3, color=color,
                              label=title if index == 0 else None)
        axis.set_yticks(range(len(fields)), [name for _, name in fields])
        axis.invert_yaxis()
        axis.set_xlabel(label)
        axis.grid(axis="x", alpha=0.25)
    axes[0].legend()
    figure.suptitle("Pinned Rust graph fixture — median and p10–p90")
    figure.savefig(output, dpi=160)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=HERE / "evidence.json")
    parser.add_argument("--output", type=Path, default=HERE / "comparison.png")
    args = parser.parse_args()
    chart(args.input, args.output)
