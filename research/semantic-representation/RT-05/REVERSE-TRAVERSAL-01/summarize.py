"""Summarize paired reverse traversal samples and reproduce the figure."""

import argparse
from collections import defaultdict
import csv
from hashlib import sha256
import json
from pathlib import Path
from random import Random
from statistics import median, quantiles

import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent
SHAPES = ("chain", "star", "layered-eight")
FIELDS = ("build_ns", "index_ns", "rebuild_batch_ns", "retained_batch_ns",
          "process_peak_kib", "live_store_bytes", "live_index_bytes")


def grouped(directory):
    config = json.loads((directory / "config.json").read_text())
    with (directory / "samples.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    groups = defaultdict(list)
    block_profiles = defaultdict(set)
    for row in rows:
        key = row["shape"], int(row["nodes"])
        block = int(row["block"])
        if key in block_profiles[block] or any(int(row[field]) <= 0 for field in FIELDS):
            raise ValueError(row)
        block_profiles[block].add(key)
        groups[key].append(row)
    if set(block_profiles) != set(range(config["trials"])) or len(groups) != 6:
        raise ValueError("incomplete trial groups")
    if any(choices != set(groups) for choices in block_profiles.values()):
        raise ValueError("missing workload from a trial block")
    return groups


def distribution(series):
    cuts = quantiles(series, n=10, method="inclusive")
    return {"median": median(series), "p10": cuts[0], "p90": cuts[-1], "n": len(series)}


def speedup(series, rng):
    boot = [median(rng.choices(series, k=len(series))) for _ in range(2000)]
    cuts = quantiles(boot, n=40, method="inclusive")
    return {"median": median(series), "bootstrap_95_interval": [cuts[0], cuts[-1]]}


def summarize(directory):
    groups = grouped(directory)
    results = {}
    rng = Random(18257)
    for (shape, size), rows in sorted(groups.items()):
        identities = {tuple(row[k] for k in ("edges", "queries", "payload_bytes", "observations_sha256")) for row in rows}
        if len(identities) != 1:
            raise ValueError("disagreement over benchmark inputs or effects")
        edges, queries, payload, observations = next(iter(identities))
        totals = [int(row["index_ns"]) + int(row["retained_batch_ns"]) for row in rows]
        speedups = [int(row["rebuild_batch_ns"]) / elapsed for row, elapsed in zip(rows, totals, strict=True)]
        results[f"{shape}/{size}"] = {
            "edges": int(edges), "queries": int(queries), "payload_bytes": int(payload),
            "observations_sha256": observations, "retained_including_setup_ns": distribution(totals),
            "paired_speedup_including_setup": speedup(speedups, rng),
            **{field: distribution([int(row[field]) for row in rows]) for field in FIELDS},
        }
    report = {"samples_sha256": sha256((directory / "samples.csv").read_bytes()).hexdigest(), "profiles": results}
    (directory / "summary.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    return results


def chart(directory, results):
    figure, axes = plt.subplots(1, 2, figsize=(10.5, 4.0), layout="constrained")
    labels = [f"{shape}, {nodes:,}" for nodes in (1024, 8192) for shape in SHAPES]
    profiles = [f"{shape}/{nodes}" for nodes in (1024, 8192) for shape in SHAPES]
    for index, name in enumerate(profiles):
        entry = results[name]
        for key, color, delta in (("rebuild_batch_ns", "#176183", -0.13),
                                  ("retained_including_setup_ns", "#8c4528", 0.13)):
            d = entry[key]
            median_ms = d["median"] / 1e6
            errors = [[median_ms - d["p10"] / 1e6], [d["p90"] / 1e6 - median_ms]]
            label = {"rebuild_batch_ns": "Rebuild for each query",
                     "retained_including_setup_ns": "Retain once, including setup"}[key] if index == 0 else None
            axes[0].errorbar(median_ms, index + delta, xerr=errors, fmt="o", capsize=3, color=color, label=label)
        axes[1].barh(index, entry["live_index_bytes"]["median"] / 2**20, height=0.5, color="#4b785a")
    axes[0].set_yticks(range(len(labels)), labels)
    axes[0].invert_yaxis()
    axes[0].set_xscale("log")
    axes[0].set_xlabel("Time for six queries (ms, log scale)")
    axes[0].legend()
    axes[1].set_yticks(range(len(labels)), labels)
    axes[1].invert_yaxis()
    axes[1].set_xlabel("Live retained index allocations (MiB)")
    for axis in axes:
        axis.grid(axis="x", alpha=0.25)
    figure.suptitle("Synthetic ContentStore graph traversal — median and p10–p90")
    figure.savefig(directory / "comparison.png", dpi=160)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, default=HERE / "evidence")
    args = parser.parse_args()
    chart(args.evidence_dir, summarize(args.evidence_dir))
