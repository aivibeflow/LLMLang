"""Check canonicalization trial ledgers and plot phase costs."""

import argparse
from collections import defaultdict
import csv
from hashlib import sha256
import json
from pathlib import Path
from statistics import median, quantiles

import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent
PHASES = ("encode", "hash", "encode_hash", "retained_hash")
LABELS = ("Encode", "SHA-256", "Encode + SHA-256", "Retained lookup + SHA-256")


def distribution(values):
    deciles = quantiles(values, n=10, method="inclusive")
    return {"median": median(values), "p10": deciles[0], "p90": deciles[-1], "n": len(values)}


def summarize(directory):
    config = json.loads((directory / "config.json").read_text())
    cohorts = defaultdict(list)
    with (directory / "samples.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        key = row["shape"], int(row["entries_per_object"])
        cohorts[key].append(row)
    if len(cohorts) != 6:
        raise ValueError("incomplete workload matrix")
    results = {}
    for (shape, entries), cohort in sorted(cohorts.items()):
        if sorted(int(row["batch"]) for row in cohort) != list(range(config["trials"])):
            raise ValueError((shape, entries, "missing or duplicate trial"))
        profile = {tuple(row[name] for name in ("invocations_per_scope", "retained_canonical_bytes",
                                                "observation_sha256")) for row in cohort}
        [(invocations, retained, digest)] = profile
        variants = {}
        for phase in PHASES:
            values = [int(row[f"{phase}_ns"]) / int(invocations) for row in cohort]
            if any(value <= 0 for value in values):
                raise ValueError((shape, entries, phase))
            variants[phase] = distribution(values)
        with_setup = [(int(row["retained_hash_ns"]) + int(row["cache_setup_ns"])) / int(invocations) for row in cohort]
        results[f"{shape}/{entries}"] = {
            "invocations_per_scope": int(invocations), "retained_canonical_bytes": int(retained),
            "observations_sha256": digest, "phase_ns_per_object": variants,
            "retained_including_setup_ns_per_object": distribution(with_setup),
            "setup_per_four_objects_ns": distribution([int(row["cache_setup_ns"]) for row in cohort]),
        }
    value = {"samples_sha256": sha256((directory / "samples.csv").read_bytes()).hexdigest(), "profiles": results}
    (directory / "summary.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return results


def chart(directory, results):
    figure, axes = plt.subplots(1, 2, figsize=(10, 4.2), layout="constrained", sharey=True)
    for shape, axis in zip(("flat", "nested"), axes, strict=True):
        for phase, label in zip(PHASES, LABELS, strict=True):
            points = [results[f"{shape}/{items}"]["phase_ns_per_object"][phase] for items in (8, 64, 512)]
            values = [point["median"] / 1000 for point in points]
            lows = [(point["median"] - point["p10"]) / 1000 for point in points]
            highs = [(point["p90"] - point["median"]) / 1000 for point in points]
            axis.errorbar((8, 64, 512), values, yerr=[lows, highs], marker="o", capsize=3, label=label)
        axis.set_xscale("log", base=2)
        axis.set_yscale("log")
        axis.set_title(shape.title())
        axis.set_xticks((8, 64, 512), labels=["8", "64", "512"])
        axis.set_xlabel("Entries per object")
        axis.grid(alpha=0.25)
    axes[0].set_ylabel("Microseconds per object (median and p10–p90)")
    axes[0].legend(fontsize=8)
    figure.suptitle("Semantic JSON encoding versus SHA-256")
    figure.savefig(directory / "costs.png", dpi=160)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, default=HERE / "evidence")
    args = parser.parse_args()
    chart(args.evidence_dir, summarize(args.evidence_dir))
