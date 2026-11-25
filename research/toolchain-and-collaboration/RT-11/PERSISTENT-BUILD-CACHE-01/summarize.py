"""Summarize verified persistent and forced build measurements."""

import argparse
from collections import defaultdict
import csv
from hashlib import sha256
import json
from pathlib import Path
from statistics import median, quantiles

import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent
PHASES = ("forced", "cold", "restored", "policy-changed")
HITS = (0, 0, 10, 9)


def distribution(samples):
    cuts = quantiles(samples, n=10, method="inclusive")
    return {"median": median(samples), "p10": cuts[0], "p90": cuts[-1], "n": len(samples)}


def summarize(directory):
    config = json.loads((directory / "config.json").read_text())
    groups = defaultdict(list)
    with (directory / "samples.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            groups[row["phase"]].append(row)
    if set(groups) != set(PHASES) or config["corruption_controls"] != config["trials"]:
        raise ValueError("incomplete benchmark matrix")
    identities = {}
    result = {}
    for phase, hit_count in zip(PHASES, HITS, strict=True):
        reports = groups[phase]
        if sorted(int(row["trial"]) for row in reports) != list(range(config["trials"])):
            raise ValueError(f"missing or repeated trial: {phase}")
        if any(int(row["hits"]) != hit_count or int(row["restored"]) != hit_count
               or not 0 < int(row["build_ns"]) < int(row["process_ns"]) for row in reports):
            raise ValueError(f"incorrect action counts or timing boundary: {phase}")
        [identities[phase]] = {row["artifacts_sha256"] for row in reports}
        result[phase] = {
            "hits": hit_count, "total_actions": 10, "artifact_sha256": identities[phase],
            **{field: distribution([int(row[field]) for row in reports])
               for field in ("build_ns", "process_ns", "cache_bytes")},
        }
    if len({identities[name] for name in ("forced", "cold", "restored")}) != 1:
        raise ValueError("phase identity mismatch")
    if identities["policy-changed"] == identities["restored"]:
        raise ValueError("verifier policy failed to alter the receipt")
    value = {"phases": result, "samples_sha256": sha256((directory / "samples.csv").read_bytes()).hexdigest()}
    (directory / "summary.json").write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    return result


def chart(directory, results):
    figure, axis = plt.subplots(figsize=(8, 3.6), layout="constrained")
    for offset, (key, label, color) in zip((-0.12, 0.12),
            (("build_ns", "Inner build and cache transaction", "#176183"),
             ("process_ns", "Full subprocess", "#a04428")), strict=True):
        for index, phase in enumerate(PHASES):
            stats = results[phase][key]
            center = stats["median"] / 1e6
            bounds = [[center - stats["p10"] / 1e6], [stats["p90"] / 1e6 - center]]
            axis.errorbar(center, index + offset, xerr=bounds, fmt="o", capsize=3,
                          label=label if index == 0 else None, color=color)
    axis.set_yticks(range(len(PHASES)), ("Forced build", "Cold SQLite", "Restore all artifacts", "Verifier policy edit"))
    axis.invert_yaxis()
    axis.set_xscale("log")
    axis.set_xlabel("Milliseconds per phase (median and p10–p90)")
    axis.legend()
    axis.grid(axis="x", alpha=0.25)
    figure.savefig(directory / "times.png", dpi=160)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, default=HERE / "evidence")
    args = parser.parse_args()
    chart(args.evidence_dir, summarize(args.evidence_dir))
