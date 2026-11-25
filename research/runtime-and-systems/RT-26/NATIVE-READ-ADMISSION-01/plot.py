"""Plot process-batched admission and refusal distributions."""

from collections import defaultdict
import json
from pathlib import Path
from statistics import median, quantiles

import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent
data = json.loads((HERE / "samples.json").read_text())["samples"]
groups = defaultdict(list)
for row in data:
    groups[row["workers"], row["policy"]].append(row)


def tail(values):
    return quantiles(values, n=100, method="inclusive")[98]


def summary(values):
    p10, *_, p90 = quantiles(values, n=10, method="inclusive")
    return f"{median(values):.2f} [{p10:.2f}, {p90:.2f}]"


variants = {
    "Median admission (ns)": lambda row: median(row["admit_ns"]),
    "Median refusal (ns)": lambda row: median(row["refuse_ns"]),
    "Refusal p99 (ns)": lambda row: tail(row["refuse_ns"]),
    "Batch elapsed (µs)": lambda row: row["elapsed_ns"] / 1_000,
}
keys = sorted(groups)
fig, axes = plt.subplots(1, 4, figsize=(12, 4.5), sharey=True, layout="constrained")
for axis, (label, extract) in zip(axes, variants.items()):
    points = [[extract(row) for row in groups[key]] for key in keys]
    axis.boxplot(points, vert=False, tick_labels=[f"{n} / {route}" for n, route in keys])
    axis.grid(axis="x", alpha=0.25)
    axis.set_xlabel(label)
    axis.set_xscale("log")
axes[0].invert_yaxis()
fig.suptitle("Task and ancestor read admission on native Linux")
fig.savefig(HERE / "admission.png", dpi=145, metadata={"Software": "Matplotlib"})
for key in keys:
    print(*key, *(summary([extract(row) for row in groups[key]]) for extract in variants.values()), sep=" | ")
