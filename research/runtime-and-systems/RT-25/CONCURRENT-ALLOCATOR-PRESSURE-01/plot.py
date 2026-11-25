"""Chart bounded concurrent reservation rates and first terminal-phase latency."""

from collections import defaultdict
import json
from pathlib import Path
from statistics import median

import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent
samples = json.loads((HERE / "samples.json").read_text())["samples"]
providers = ("glibc", "jemalloc", "mimalloc", "gperftools", "google")
groups = defaultdict(list)
for row in samples:
    groups[row["provider"], row["workers"], row["cap_mib"], row["cap_before_workers"]].append(row)
fig, axes = plt.subplots(2, 4, figsize=(14, 6), layout="constrained", sharey=True)

for column, (cap, early) in enumerate(((96, True), (96, False), (192, True), (192, False))):
    chosen = [groups[name, 4, cap, early] for name in providers]
    size = [[4 * sum(worker["held"] for worker in row["per_thread"])
             for row in group if "per_thread" in row] for group in chosen]
    elapsed = [[max(worker["reserve_ns"] for worker in row["per_thread"]) / 1000
                for row in group if "per_thread" in row] for group in chosen]
    tag = "before workers" if early else "after warmup"
    axes[0, column].set_title(f"{cap} MiB {tag}")
    for axis, values, label in ((axes[0, column], size, "Retained payload (MiB)"),
                                (axes[1, column], elapsed, "Slowest worker (µs)")):
        for i, values_for_provider in enumerate(values, start=1):
            if values_for_provider:
                axis.boxplot([values_for_provider], vert=False, positions=[i], widths=0.5, manage_ticks=False)
            else:
                axis.text(0.03, i, "startup refused", transform=axis.get_yaxis_transform(), va="center", fontsize=8)
        axis.set_yticks(range(1, 6), providers)
        axis.grid(axis="x", alpha=0.25)
        axis.set_xlabel(label)
axes[0, 0].invert_yaxis()
fig.suptitle("Four-worker allocator pressure · seven processes per policy")
fig.savefig(HERE / "pressure.png", dpi=145, metadata={"Software": "Matplotlib"})

for key, group in sorted(groups.items()):
    started = [row["per_thread"] for row in group if "per_thread" in row]
    chunks = [sum(worker["held"] for worker in workers) for workers in started]
    elapsed_us = [max(worker["reserve_ns"] for worker in workers) / 1000 for workers in started]
    retry = [worker["retried"] for workers in started for worker in workers]
    print(*key, len(started), tuple((min(chunks), median(chunks), max(chunks))) if chunks else None,
          round(median(elapsed_us), 2) if elapsed_us else None, sum(retry), len(retry), sep=" | ")
