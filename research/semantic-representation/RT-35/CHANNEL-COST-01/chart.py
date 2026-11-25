"""Render timing ranges and feature payload sizes from archived measurements."""

import json
from pathlib import Path

import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent
data = json.loads((HERE / "evidence.json").read_text())
channels = ("structured", "lexical", "single_vector", "multi_aspect", "hybrid")
labels = ("Structured", "Lexical", "Single vector", "Multi-aspect", "Hybrid")
figure, axes = plt.subplots(1, 3, figsize=(10, 3.6), layout="constrained", sharey=True)
measurements = (
    ("query_batch_ns", 1_000_000, "36-query batch (ms)"),
    ("row_update_ns", 1_000, "One row replacement (µs)"),
)
for axis, (metric, scale, title) in zip(axes, measurements):
    for i, channel in enumerate(channels):
        sample = data["summary"][channel][metric]
        axis.hlines(i, sample["p10"] / scale, sample["p90"] / scale, color="#155663", lw=2)
        axis.plot(sample["median"] / scale, i, "o", color="#155663", ms=5)
    axis.set_xlabel(title)
axes[2].barh(labels, [data["serialized_feature_bytes"][ch] / 1024 for ch in channels],
             height=.45, color="#53647f")
axes[2].set_xlabel("Feature payload (KiB)")
axes[0].invert_yaxis()
for axis in axes:
    axis.set_xlim(left=0)
    axis.grid(axis="x", alpha=.22)
    axis.spines[["top", "right"]].set_visible(False)
figure.suptitle("RT-35 retrieval channel costs on the scoped corpus")
figure.savefig(HERE / "channel-cost.png", dpi=150)
