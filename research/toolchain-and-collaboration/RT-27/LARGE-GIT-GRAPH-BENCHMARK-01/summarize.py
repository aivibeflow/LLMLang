"""Validate Git graph trial ledgers and reproduce the distribution chart."""

import argparse
from collections import defaultdict
import csv
from hashlib import sha256
import json
from pathlib import Path
from statistics import median, quantiles

import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent
PHASES = ("clone_ns", "verify_ns", "traversal_ns")
LABELS = ("Clean clone and checkout", "Read and verify graph", "Five exact closure queries")


def distribution(values):
    deciles = quantiles(values, n=10, method="inclusive")
    return {"median": median(values), "p10": deciles[0], "p90": deciles[-1], "n": len(values)}


def summarize(directory):
    settings = json.loads((directory / "config.json").read_text())
    cohorts = defaultdict(list)
    with (directory / "samples.csv").open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            cohorts[row["degree"]].append(row)
    profiles = {}
    if set(cohorts) != set(settings["repositories"]):
        raise ValueError("incomplete workload profiles")
    for degree, rows in sorted(cohorts.items(), key=lambda item: int(item[0])):
        if sorted(int(row["trial"]) for row in rows) != list(range(settings["trials"])):
            raise ValueError("incomplete measurements")
        [(count, roots, closure)] = {(row["edges"], row["roots"], row["closure_sizes"]) for row in rows}
        size = settings["nodes"]
        if int(count) != (size - settings["layer_width"]) * int(degree) or int(roots) != len(settings["roots"]):
            raise ValueError("incorrect workload size")
        identity = settings["repositories"][degree]
        profiles[degree] = {
            "nodes": size, "edges": int(count), "roots": int(roots),
            "closure_sizes": [int(value) for value in closure.split(",")],
            "pack_bytes": identity["pack_bytes"], "checkout_bytes": identity["checkout_bytes"],
            **{key: distribution([int(row[key]) for row in rows]) for key in PHASES},
        }
    report = {"profiles": profiles, "samples_sha256": sha256((directory / "samples.csv").read_bytes()).hexdigest()}
    (directory / "summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return profiles


def chart(directory, profiles):
    figure, (timing, storage) = plt.subplots(1, 2, figsize=(10, 3.6), layout="constrained")
    keys = sorted(profiles, key=int)
    ticks = [f"{key} dependencies per linked node" for key in keys]
    colors = ("#216991", "#904a27", "#4b785a")
    for phase, label, color, offset in zip(PHASES, LABELS, colors, (-0.2, 0, 0.2), strict=True):
        for i, key in enumerate(keys):
            result = profiles[key][phase]
            center = result["median"] / 1e6
            bars = [[center - result["p10"] / 1e6], [result["p90"] / 1e6 - center]]
            timing.errorbar(center, i + offset, xerr=bars, marker="o", capsize=3, color=color,
                            label=label if i == 0 else None)
    timing.set_xscale("log")
    timing.set_xlabel("Milliseconds (median and p10–p90)")
    for key, label, offset, color in (("pack_bytes", "Source repository pack", -0.18, "#667097"),
                                      ("checkout_bytes", "Active payload files", 0.18, "#4b785a")):
        storage.barh([i + offset for i in range(len(keys))],
                     [profiles[degree][key] / 2**20 for degree in keys], color=color, label=label, height=0.28)
    storage.set_xlabel("Stored bytes (MiB)")
    for axis in (timing, storage):
        axis.set_yticks(range(len(keys)), ticks)
        axis.invert_yaxis()
        axis.legend(fontsize=7)
        axis.grid(axis="x", alpha=0.25)
    figure.suptitle("Git reconstruction of 65,536-node synthetic graphs")
    figure.savefig(directory / "phases.png", dpi=160)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, default=HERE / "evidence")
    args = parser.parse_args()
    chart(args.evidence_dir, summarize(args.evidence_dir))
