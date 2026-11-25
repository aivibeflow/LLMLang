"""Render the preserved diamond traversal measurements and exact visit counts."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
SCALES = {"paths": ("Enumerate paths", "o", "-"), "full-state": ("Coalesce exact state", "s", "--")}


def render(ledger, output):
    plt.rcParams["svg.hashsalt"] = "llmlang-diamond-traversal-v1"
    rows = ledger["rows"]
    depths = [row["depth"] for row in rows]
    figure, (left, right) = plt.subplots(1, 2, figsize=(9, 3.4), layout="constrained")
    for method, (label, marker, line) in SCALES.items():
        visits = [row["complete_visits"][method] for row in rows]
        left.plot(depths, visits, label=label, marker=marker, linestyle=line)
        times = [row["elapsed"][method] for row in rows]
        median = [item["median_ns_per_traversal"] / 1e3 for item in times]
        low = [(item["median_ns_per_traversal"] - item["q1_ns_per_traversal"]) / 1e3 for item in times]
        high = [(item["q3_ns_per_traversal"] - item["median_ns_per_traversal"]) / 1e3 for item in times]
        right.errorbar(depths, median, yerr=(low, high), marker=marker, linestyle=line, capsize=3)
    for axis in (left, right):
        axis.set_yscale("log")
        axis.set_xticks(depths)
        axis.set_xlabel("Diamond layers")
        axis.grid(axis="y", alpha=0.3)
    left.set_title("Traversal work")
    left.set_ylabel("Visited states (log scale)")
    left.legend(loc="upper left", fontsize=8)
    right.set_title(f"Timed traversal, n={ledger['trials_per_profile']} trials")
    right.set_ylabel("Median per traversal (µs, log scale)")
    metadata = {"Creator": f"Matplotlib {matplotlib.__version__}"}
    if output.suffix.lower() == ".svg":
        metadata["Date"] = None
    figure.savefig(output, metadata=metadata)
    plt.close(figure)
    if output.suffix.lower() == ".svg":
        lines = output.read_text(encoding="utf-8").splitlines()
        output.write_text("\n".join(line.rstrip() for line in lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=HERE / "evidence.json")
    parser.add_argument("--output", type=Path, default=HERE / "diamond-traversal.svg")
    settings = parser.parse_args()
    render(json.loads(settings.input.read_text()), settings.output)
