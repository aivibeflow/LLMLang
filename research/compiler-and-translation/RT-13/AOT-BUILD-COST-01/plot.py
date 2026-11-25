"""Summarize medians and p10/p90 over independent process-level batches."""

from collections import defaultdict
import json
from pathlib import Path
from statistics import median, quantiles

import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent
samples = json.loads((HERE / "samples.json").read_text())["samples"]
groups = defaultdict(list)
for row in samples:
    groups[row["family"], row["mode"]].append(row)


def stage(row, name):
    return row["stages"][name]


metrics = {
    "Clean build (ms)": lambda row: (stage(row, "clean_compile_ns") + stage(row, "clean_link_ns")) / 1e6,
    "Incremental build (ms)": lambda row: (
        stage(row, "incremental_compile_ns") + stage(row, "incremental_link_ns")
    ) / 1e6,
    "Clean compilation (objects/s)": lambda row: row["clean_objects"] * 1e9 / stage(row, "clean_compile_ns"),
    "Edited runtime (µs per batch)": lambda row: median(row["runtime_batch_ns"]["edited"]) / 1e3,
    "Edited runtime (million calls/s)": lambda row: (
        row["provider_calls_per_runtime"] * 1e3 / median(row["runtime_batch_ns"]["edited"])
    ),
    "Clean peak tool RSS (MiB)": lambda row: stage(row, "clean_peak_tool_kib") / 1024,
    "Incremental peak tool RSS (MiB)": lambda row: stage(row, "incremental_peak_tool_kib") / 1024,
    "ELF size (KiB)": lambda row: row["binary_bytes"] / 1024,
}
order = sorted(groups)
labels = [f"{family}, {mode}" for family, mode in order]
fig, axes = plt.subplots(2, 4, figsize=(15, 6.5), sharey=True, layout="constrained")
for axis, (title, evaluate) in zip(axes.flatten(), metrics.items()):
    sets = [[evaluate(row) for row in groups[key]] for key in order]
    axis.boxplot(sets, vert=False, tick_labels=labels, widths=0.6)
    axis.grid(axis="x", alpha=0.25)
    axis.set_title(title)
axes[0, 0].invert_yaxis()
fig.suptitle("Native LLVM build and runtime across 30 process-level batches")
fig.savefig(HERE / "timings.png", dpi=150, metadata={"Software": "Matplotlib"})


def summarize(values):
    p10, *_, p90 = quantiles(values, n=10, method="inclusive")
    return f"{median(values):.2f} [{p10:.2f}, {p90:.2f}]"


for key in order:
    print(*key, *(summarize([evaluate(row) for row in groups[key]]) for evaluate in metrics.values()), sep=" | ")
