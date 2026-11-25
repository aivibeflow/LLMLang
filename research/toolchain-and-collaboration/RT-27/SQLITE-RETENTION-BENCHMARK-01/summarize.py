"""Check SQLite retention measurements and recreate their timing and size figure."""

import argparse
from collections import defaultdict
import csv
from hashlib import sha256
import json
from pathlib import Path
from statistics import median, quantiles

import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent
SIZES = (2048, 8192)
VARIANTS = ("scan", "indexed")
TIMINGS = ("load_ns", "index_ns", "query_ns", "collect_ns", "vacuum_ns")
SPACE = ("before_bytes", "after_sweep_bytes", "after_vacuum_bytes", "free_pages")


def distribution(values):
    cuts = quantiles(values, n=10, method="inclusive")
    return {"median": median(values), "p10": cuts[0], "p90": cuts[-1], "n": len(values)}


def summarize(directory):
    config = json.loads((directory / "config.json").read_text())
    grouped = defaultdict(list)
    with (directory / "samples.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            grouped[(row["variant"], int(row["objects"]))].append(row)
    profiles = {}
    for size in SIZES:
        digests = set()
        for variant in VARIANTS:
            rows = grouped.pop((variant, size))
            if sorted(int(row["block"]) for row in rows) != list(range(config["trials"])):
                raise ValueError("incomplete measured profile")
            for row in rows:
                if (int(row["removed"]) != size // 2 or int(row["retained_ignored_by_active_only"]) != size // 4
                        or int(row["before_bytes"]) < int(row["after_sweep_bytes"])
                        or int(row["after_sweep_bytes"]) <= int(row["after_vacuum_bytes"])):
                    raise ValueError(row)
            [identities] = {(row["survivor_sha256"], row["edges"], row["queries"]) for row in rows}
            digest, edges, queries = identities
            digests.add(digest)
            profiles[f"{variant}/{size}"] = {
                "survivor_sha256": digest, "edges": int(edges), "queries": int(queries),
                "removed": size // 2,
                "lost_if_active_only": size // 4,
                **{key: distribution([int(row[key]) for row in rows]) for key in TIMINGS + SPACE},
            }
        if len(digests) != 1:
            raise ValueError("index variant changed survivors")
    if grouped:
        raise ValueError("unexpected benchmark profiles")
    report = {"profiles": profiles, "samples_sha256": sha256((directory / "samples.csv").read_bytes()).hexdigest()}
    (directory / "summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return profiles


def chart(directory, profiles):
    figure, axes = plt.subplots(1, 2, figsize=(10.6, 3.8), layout="constrained")
    keys = [f"{variant}/{size}" for size in SIZES for variant in VARIANTS]
    labels = [f"{variant}, {size:,}" for size in SIZES for variant in VARIANTS]
    for shift, field, label, color in ((-0.22, "query_ns", "24 lookups", "#176183"),
            (0, "collect_ns", "Mark and sweep", "#794222"), (0.22, "vacuum_ns", "VACUUM", "#468354")):
        for i, name in enumerate(keys):
            row = profiles[name][field]
            middle = row["median"] / 1e6
            bars = [[middle - row["p10"] / 1e6], [row["p90"] / 1e6 - middle]]
            axes[0].errorbar(middle, i + shift, xerr=bars, fmt="o", capsize=3,
                             color=color, label=label if i == 0 else None)
    axes[0].set_xscale("log")
    axes[0].set_xlabel("Milliseconds (median and p10–p90)")
    axes[0].legend(fontsize=8)
    for shift, field, label, color in ((-0.21, "before_bytes", "Before sweep", "#5d6492"),
                                      (0.21, "after_vacuum_bytes", "After VACUUM", "#468354")):
        axes[1].barh([i + shift for i in range(len(keys))],
                     [profiles[key][field]["median"] / 2**20 for key in keys], height=0.32,
                     color=color, label=label)
    axes[1].set_xlabel("SQLite database size (MiB)")
    axes[1].legend(fontsize=8)
    for axis in axes:
        axis.set_yticks(range(len(labels)), labels)
        axis.invert_yaxis()
        axis.grid(axis="x", alpha=0.25)
    figure.suptitle("Reverse indexing and retained-root reclamation")
    figure.savefig(directory / "profiles.png", dpi=160)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, default=HERE / "evidence")
    args = parser.parse_args()
    chart(args.evidence_dir, summarize(args.evidence_dir))
