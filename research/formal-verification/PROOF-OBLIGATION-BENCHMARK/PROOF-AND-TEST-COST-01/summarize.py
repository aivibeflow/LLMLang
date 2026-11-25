"""Validate measured proof and finite-test ledgers and plot their scope costs."""

import argparse
from collections import defaultdict
import csv
from hashlib import sha256
import json
from pathlib import Path
from statistics import median, quantiles

import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent
PROFILES = ("discovery", "multiversion", "mapping-ipc")
MODES = ("proof", "test")


def distribution(values):
    deciles = quantiles(values, n=10, method="inclusive")
    return {"median": median(values), "p10": deciles[0], "p90": deciles[-1], "n": len(values)}


def summarize(directory):
    config = json.loads((directory / "config.json").read_text())
    groups = defaultdict(list)
    with (directory / "samples.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            groups[(row["profile"], row["mode"])].append(row)
    result = {}
    for profile in PROFILES:
        for mode in MODES:
            rows = groups.pop((profile, mode))
            if sorted(int(row["batch"]) for row in rows) != list(range(config["trials"])):
                raise ValueError((profile, mode, "incomplete measurement ledger"))
            if any(not 0 < int(row["inner_ns"]) < int(row["process_ns"]) or int(row["peak_kib"]) <= 0
                   for row in rows):
                raise ValueError((profile, mode, "invalid samples"))
            [(work, receipt, archive, harness)] = {
                (int(row["work"]), row["receipt_sha256"], row["archive_sha256"], row["harness_sha256"])
                for row in rows
            }
            result[f"{profile}/{mode}"] = {
                "work": work, "receipt_sha256": receipt, "archive_sha256": archive, "harness_sha256": harness,
                **{key: distribution([int(row[key]) for row in rows]) for key in ("inner_ns", "process_ns", "peak_kib")},
            }
        if result[f"{profile}/proof"]["archive_sha256"] != result[f"{profile}/test"]["archive_sha256"]:
            raise ValueError((profile, "evidence inputs changed between phases"))
    if groups:
        raise ValueError(f"unexpected data profiles: {groups.keys()}")
    data = {"profiles": result, "sample_sha256": sha256((directory / "samples.csv").read_bytes()).hexdigest()}
    (directory / "summary.json").write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return result


def chart(directory, results):
    figure, axes = plt.subplots(1, 2, figsize=(9.2, 4), layout="constrained", sharey=True)
    for panel, key, divisor, label in zip(axes, ("inner_ns", "peak_kib"), (1e6, 1024),
            ("Inner phase time (ms, log scale)", "Recorded process peak RSS (MiB, log scale)"), strict=True):
        for offset, mode, color in ((-0.13, "proof", "#176183"), (0.13, "test", "#a04428")):
            for i, profile in enumerate(PROFILES):
                row = results[f"{profile}/{mode}"][key]
                center = row["median"] / divisor
                bounds = [[center - row["p10"] / divisor], [row["p90"] / divisor - center]]
                panel.errorbar(center, i + offset, xerr=bounds, fmt="o", capsize=3, color=color,
                               label=mode.title() if i == 0 else None)
        panel.set_yticks(range(len(PROFILES)), ("Discovery", "Multiversion", "Mapping and IPC"))
        panel.set_xscale("log")
        panel.set_xlabel(label)
        panel.grid(axis="x", alpha=0.25)
    axes[0].invert_yaxis()
    axes[0].legend()
    figure.suptitle("Proof checks and finite oracles — median and p10–p90")
    figure.savefig(directory / "phases.png", dpi=160)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, default=HERE / "evidence")
    args = parser.parse_args()
    chart(args.evidence_dir, summarize(args.evidence_dir))
