"""Summarize the paired benchmark and render a reproducible SVG."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import random
from statistics import median

MODES = ("cold", "warm", "edit", "revert")
STAGES = ("project_ns", "lookup_ns", "solve_ns", "check_ns", "publish_ns")
GENERATION = "oracle"


def quantile(values, probability):
    order = sorted(values)
    position = (len(order) - 1) * probability
    offset = int(position)
    return order[offset] + (order[min(offset + 1, len(order) - 1)] - order[offset]) * (position - offset)


def summary(csv_path):
    groups = defaultdict(list)
    with csv_path.open(newline="") as source:
        for row in csv.DictReader(source):
            for field in ("block", "value", "hit", "total_ns", "artifact_bytes", "sqlite_file_bytes",
                          "cvc5_peak_rss_kib", "carcara_peak_rss_kib", *STAGES):
                row[field] = int(row[field])
            groups[row["block"], row["mode"]].append(row)
    blocks = sorted({index for index, _ in groups})
    assert len(blocks) == 11
    result = {}
    paired = {}
    for mode in MODES:
        observations = []
        for block in blocks:
            captured = groups[block, mode]
            assert len(captured) == 12
            prices = {(row["subject"], row["value"]): row for row in groups[block, GENERATION]}
            matched = [prices[row["subject"], row["value"]] for row in captured]
            baseline = sum(row["total_ns"] for row in matched)
            actual = sum(row["total_ns"] for row in captured)
            weights = [row["solve_ns"] + row["check_ns"] for row in matched]
            hit_rate = sum(row["hit"] for row in captured) / len(captured)
            weighted_hit = sum(row["hit"] * cost for row, cost in zip(captured, weights)) / sum(weights)
            stages = {field: sum(row[field] for row in captured) / 1e6 for field in STAGES}
            observations.append({"elapsed_ms": actual / 1e6, "oracle_ms": baseline / 1e6,
                                 "oracle_over_actual": baseline / actual, "hit_rate": hit_rate,
                                 "cost_weighted_hit_rate": weighted_hit, "stage_ms": stages,
                                 "final_sqlite_bytes": captured[-1]["sqlite_file_bytes"]})
        paired[mode] = observations
        durations = [row["elapsed_ms"] for row in observations]
        ratios = [row["oracle_over_actual"] for row in observations]
        rng = random.Random(44012)
        bootstrap = [median(rng.choices(ratios, k=len(ratios))) for _ in range(3000)]
        result[mode] = {
            "median_ms": median(durations), "quartiles_ms": [quantile(durations, p) for p in (0.25, 0.75)],
            "matched_oracle_median_ms": median(row["oracle_ms"] for row in observations),
            "paired_oracle_over_actual_median": median(ratios),
            "paired_bootstrap_median_95": [quantile(bootstrap, p) for p in (0.025, 0.975)],
            "median_hit_rate": median(row["hit_rate"] for row in observations),
            "median_cost_weighted_hit_rate": median(row["cost_weighted_hit_rate"] for row in observations),
            "median_stage_ms": {field: median(row["stage_ms"][field] for row in observations) for field in STAGES},
            "median_final_sqlite_bytes": median(row["final_sqlite_bytes"] for row in observations),
        }
    raw = [row for group in groups.values() for row in group]
    distinct = sorted({row["artifact_bytes"] for row in raw})
    memory = {}
    for tool in ("cvc5", "carcara"):
        peak = [row[f"{tool}_peak_rss_kib"] for row in raw if row[f"{tool}_peak_rss_kib"]]
        memory[tool] = {"runs": len(peak), "median_peak_rss_kib": median(peak),
                        "range_peak_rss_kib": [min(peak), max(peak)]}
    return {"benchmark_rows": len(raw), "paired_blocks": len(blocks), "modes": result,
            "paired_observations": paired, "artifact_byte_range": [min(distinct), max(distinct)], "memory": memory}


def draw(result, destination):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"svg.hashsalt": "rt33-proof-cache-benchmark-01",
                         "svg.fonttype": "none",
                         "font.family": "DejaVu Sans", "font.size": 10})
    fig, (timing, hits) = plt.subplots(1, 2, figsize=(9.0, 3.7))
    mode_names = ["Cold", "Warm", "Edit", "Revert"]
    for index, mode in enumerate(MODES):
        observations = result["paired_observations"][mode]
        measured = [sample["elapsed_ms"] for sample in observations]
        x = [index + (position - 5) * 0.025 for position in range(len(measured))]
        timing.scatter(x, measured, s=18, color="#487ab4", alpha=0.6)
        timing.scatter(index, result["modes"][mode]["median_ms"], marker="_", s=210, color="#162f49")
        hits.scatter(index, result["modes"][mode]["median_hit_rate"] * 100,
                     marker="o", s=38, color="#145e72", label="By count" if index == 0 else None)
        hits.scatter(index, result["modes"][mode]["median_cost_weighted_hit_rate"] * 100,
                     marker="x", s=75, color="#973c16", label="Cost weighted" if index == 0 else None)
    timing.set_yscale("log")
    timing.set_ylabel("Milliseconds per 12 tasks")
    timing.set_title("Elapsed wall time")
    hits.set_ylabel("Cache hit rate (%)")
    hits.set_title("Hit rates")
    hits.set_ylim(-6, 110)
    hits.legend(loc="center left", fontsize=8, frameon=False)
    for axis in (timing, hits):
        axis.set_xticks(range(len(MODES)), mode_names)
        axis.grid(axis="y", alpha=0.24)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
    fig.suptitle("RT-33 proof cache on 11 paired blocks", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(destination, metadata={"Date": None}, bbox_inches="tight")
    svg = destination.read_text()
    destination.write_text("\n".join(line.rstrip() for line in svg.splitlines()) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("json", type=Path)
    parser.add_argument("chart", type=Path)
    args = parser.parse_args()
    result = summary(args.csv)
    args.json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    draw(result, args.chart)


if __name__ == "__main__":
    main()
