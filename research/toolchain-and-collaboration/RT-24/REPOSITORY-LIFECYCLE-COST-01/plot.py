"""Plot exact measured samples and print median and range by workload."""

from collections import defaultdict
import json
from pathlib import Path
from statistics import median

import matplotlib.pyplot as plt


directory = Path(__file__).parent
data = json.loads((directory / "samples.json").read_text())
groups = defaultdict(lambda: defaultdict(list))
for sample in data["samples"]:
    key = sample["tracked_modules"], sample["changed_modules"]
    for stage, elapsed in sample["ns"].items():
        groups[key][stage].append(elapsed / 1_000_000)

stages = {
    "native_git_merge": "Native Git merge",
    "full_semantic_import": "Semantic import",
    "full_semantic_export": "Full export",
    "incremental_worktree_sync": "Incremental writes",
    "fresh_sqlite_cache_rebuild": "SQLite rebuild",
}
keys = sorted(groups)
fig, axes = plt.subplots(1, len(stages), sharey=True, figsize=(12, 4.2), layout="constrained")
for axis, (stage, caption) in zip(axes, stages.items()):
    points = [groups[key][stage] for key in keys]
    axis.boxplot(points, vert=False, widths=0.55, tick_labels=[f"{n} / {d}" for n, d in keys])
    axis.set_title(caption)
    axis.set_xscale("log")
    axis.set_xlabel("Milliseconds")
    axis.grid(axis="x", alpha=0.25)
axes[0].set_ylabel("Tracked modules / changed modules")
axes[0].invert_yaxis()
fig.suptitle("Repository lifecycle stages across nine native runs per workload")
fig.savefig(directory / "timings.png", dpi=145, metadata={"Software": "Matplotlib"})
for key in keys:
    print(*key, *(
        f"{median(groups[key][stage]):.3f} [{min(groups[key][stage]):.3f}, {max(groups[key][stage]):.3f}]"
        for stage in stages
    ), sep=" | ")
