"""Verify publication outcomes and summarize elapsed, wait and retry costs."""

import argparse
from collections import defaultdict
import csv
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
from statistics import median, quantiles

import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent
WRITERS = (2, 4, 8)
SHAPES = ("independent", "duplicate")
POLICIES = ("whole-head", "exact-projection")


def stats(values):
    cuts = quantiles(values, n=10, method="inclusive")
    return {"median": median(values), "p10": cuts[0], "p90": cuts[-1], "n": len(values)}


def summarize(directory):
    settings = json.loads((directory / "config.json").read_text())
    grouped = defaultdict(list)
    with (directory / "samples.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            grouped[(int(row["writers"]), row["shape"], row["policy"])].append(row)
    results = {}
    for writers, shape, policy in product(WRITERS, SHAPES, POLICIES):
        rows = grouped.pop((writers, shape, policy))
        if sorted(int(r["block"]) for r in rows) != list(range(settings["trials"])):
            raise ValueError("incomplete or duplicate trials")
        commits = 1 if shape == "duplicate" else writers
        for row in rows:
            retry = int(row["retries"])
            if int(row["commits"]) != commits or int(row["refusals"]) != writers - commits:
                raise ValueError("unexpected merge outcomes")
            if policy == "exact-projection" and (retry or int(row["write_attempts"]) != writers):
                raise ValueError("exact comparison counted a retry")
            if policy == "whole-head" and retry < writers - 1:
                raise ValueError("whole-head CAS did not account for stale proposals")
        [digest] = {row["final_edges_sha256"] for row in rows}
        results[f"{shape}/{writers}/{policy}"] = {
            "commits": commits, "refusals": writers - commits, "final_edges_sha256": digest,
            **{key: stats([int(row[key]) for row in rows]) for key in
               ("batch_ns", "total_wait_ns", "max_wait_ns", "total_hold_ns", "retries", "write_attempts")},
            "commits_per_second": stats([1e9 * commits / int(row["batch_ns"]) for row in rows]),
        }
    if grouped:
        raise ValueError("unknown comparison cell")
    for writers, shape in product(WRITERS, SHAPES):
        values = {results[f"{shape}/{writers}/{policy}"]["final_edges_sha256"] for policy in POLICIES}
        if len(values) != 1:
            raise ValueError("the final graph changed across policies")
    report = {"profiles": results, "samples_sha256": sha256((directory / "samples.csv").read_bytes()).hexdigest()}
    (directory / "summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return results


def chart(directory, results):
    figure, axes = plt.subplots(1, 2, figsize=(9, 3.6), layout="constrained", sharey=True)
    for axis, shape in zip(axes, SHAPES, strict=True):
        for policy, color in zip(POLICIES, ("#765122", "#176183"), strict=True):
            durations = [results[f"{shape}/{writers}/{policy}"]["batch_ns"] for writers in WRITERS]
            values = [row["median"] / 1e6 for row in durations]
            errors = [[(row["median"] - row["p10"]) / 1e6 for row in durations],
                      [(row["p90"] - row["median"]) / 1e6 for row in durations]]
            axis.errorbar(WRITERS, values, yerr=errors, fmt="o-", capsize=3, label=policy, color=color)
        axis.set_title(f"{shape.capitalize()} proposals")
        axis.set_xticks(WRITERS)
        axis.set_xlabel("Concurrent writers")
        axis.grid(alpha=0.25)
    axes[0].set_ylabel("Publication batch time (ms, median and p10–p90)")
    axes[0].legend()
    figure.savefig(directory / "batch-times.png", dpi=160)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, default=HERE / "evidence")
    args = parser.parse_args()
    chart(args.evidence_dir, summarize(args.evidence_dir))
