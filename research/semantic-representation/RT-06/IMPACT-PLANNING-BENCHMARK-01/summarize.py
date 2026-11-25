"""Validate paired impact-planning measurements and plot phase distributions."""

import argparse
from collections import defaultdict
import csv
from hashlib import sha256
import json
from pathlib import Path
from statistics import median, quantiles

import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent
SHAPES = ("spread", "hot")
SIZES = (64, 256, 1024)
FIELDS = ("discovery_ns", "audit_ns", "bind_ns", "baseline_plan_ns", "grouped_plan_ns")


def stats(values):
    cuts = quantiles(values, n=10, method="inclusive")
    return {"median": median(values), "p10": cuts[0], "p90": cuts[-1], "n": len(values)}


def summarize(directory):
    config = json.loads((directory / "config.json").read_text())
    with (directory / "samples.csv").open(newline="", encoding="utf-8") as stream:
        raw = list(csv.DictReader(stream))
    groups = defaultdict(list)
    for row in raw:
        if any(int(row[key]) <= 0 for key in FIELDS):
            raise ValueError(row)
        groups[(row["shape"], int(row["active_callers"]))].append(row)
    result = {}
    for shape in SHAPES:
        for size in SIZES:
            rows = groups.pop((shape, size))
            if sorted(int(row["block"]) for row in rows) != list(range(config["trials"])):
                raise ValueError((shape, size, "missing or duplicate trial"))
            [(edge_count, plan_id, grouped_source)] = {
                (int(row["incoming_edges"]), row["plan_id"], row["grouped_source_sha256"]) for row in rows
            }
            if edge_count != (size if shape == "hot" else size // 8):
                raise ValueError((shape, size, edge_count))
            result[f"{shape}/{size}"] = {
                "incoming_edges": edge_count, "plan_id": plan_id, "grouped_source_sha256": grouped_source,
                "planner_paired_ratio": stats([int(row["baseline_plan_ns"]) / int(row["grouped_plan_ns"]) for row in rows]),
                **{key: stats([int(row[key]) for row in rows]) for key in FIELDS},
            }
    if groups:
        raise ValueError("unknown workload profiles were present")
    report = {"samples_sha256": sha256((directory / "samples.csv").read_bytes()).hexdigest(), "profiles": result}
    (directory / "summary.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    return result


def chart(directory, profiles):
    figure, axes = plt.subplots(1, 2, figsize=(10.5, 4.2), layout="constrained", sharey=True)
    labels = ("Discover", "Independent audit", "Rebuild and bind evidence", "Original plan", "Grouped plan")
    for axis, shape in zip(axes, SHAPES, strict=True):
        for label, phase in zip(labels, FIELDS, strict=True):
            series = [profiles[f"{shape}/{size}"][phase] for size in SIZES]
            mid = [float(row["median"]) / 1e6 for row in series]
            lower = [(row["median"] - row["p10"]) / 1e6 for row in series]
            upper = [(row["p90"] - row["median"]) / 1e6 for row in series]
            axis.errorbar(SIZES, mid, yerr=[lower, upper], marker="o", capsize=3, label=label)
        axis.set_xscale("log", base=2)
        axis.set_yscale("log")
        axis.set_xticks(SIZES, labels=[f"{size:,}" for size in SIZES])
        axis.set_xlabel("Active callers in selected snapshot")
        axis.set_title(f"{shape.title()} callee distribution")
        axis.grid(alpha=0.25)
    axes[0].set_ylabel("Milliseconds per phase (median and p10–p90)")
    axes[0].legend(fontsize=7)
    figure.suptitle("Dependency discovery and impact planning")
    figure.savefig(directory / "phases.png", dpi=160)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, default=HERE / "evidence")
    args = parser.parse_args()
    chart(args.evidence_dir, summarize(args.evidence_dir))
