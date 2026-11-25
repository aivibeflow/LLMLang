"""Render logical evidence-storage byte counts from the study ledger."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
LAYOUTS = {
    "bundle": ("One bundle", "#9c432c", "o"),
    "embedded_per_receipt": ("Payload per receipt", "#245cb2", "s"),
    "shared_payload": ("Shared payload", "#197344", "D"),
}


def main():
    data = json.loads((HERE / "evidence.json").read_text())["measurements"]
    counts = [int(n) for n in data]
    plt.rcParams.update({"svg.hashsalt": "llmlang-rt05-evidence-granularity", "font.size": 10})
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 4.1), sharey=True, layout="constrained")
    for axis, label, field in zip(
        axes,
        ("Original evidence set", "New objects after one subject revision"),
        ("old_bytes", "new_unique_bytes"),
    ):
        for layout, (name, color, marker) in LAYOUTS.items():
            values = [data[str(n)]["subject_only"][layout][field] / 1024 for n in counts]
            axis.plot(counts, values, label=name, color=color, marker=marker, linewidth=1.7)
        axis.set(title=label, xlabel="Receipts in the set", xscale="log", yscale="log")
        axis.set_xticks(counts, [str(n) for n in counts])
        axis.grid(True, axis="y", which="major", alpha=0.22)
    axes[0].set_ylabel("Logical data (KiB)")
    axes[1].legend(loc="upper left", frameon=True)
    target = HERE / "logical-evidence-bytes.svg"
    fig.savefig(target, metadata={"Date": None})
    target.write_text("\n".join(line.rstrip() for line in target.read_text().splitlines()) + "\n")
    plt.close(fig)


if __name__ == "__main__":
    main()
