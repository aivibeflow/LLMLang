"""Verify the paired measurement ledger and summarize per-profile distributions."""

import argparse
import csv
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
from random import Random
from statistics import median, quantiles

import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
PROFILES = ("llvm-O0", "llvm-O3", "cranelift-none", "cranelift-speed")
MEASURES = {
    "process_ns": (1e6, "Spawn through result and exit (ms)"),
    "jit_ns": (1e6, "In-process materialization (ms)"),
    "child_peak_kib": (1024, "Child peak RSS (MiB)"),
}


def distribution(series):
    percentiles = quantiles(series, n=10, method="inclusive")
    return {"n": len(series), "p10": percentiles[0], "median": median(series), "p90": percentiles[-1]}


def read_ledger(directory):
    config = json.loads((directory / "config.json").read_text())
    with (directory / "samples.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    batches = config["batches"]
    if len(rows) != batches * len(PROFILES):
        raise ValueError(f"incomplete ledger: {directory}")
    random = Random(config["seed"])
    for batch in range(batches):
        order = list(PROFILES)
        random.shuffle(order)
        block = rows[batch * len(PROFILES):(batch + 1) * len(PROFILES)]
        for index, (profile, row) in enumerate(zip(order, block, strict=True)):
            if (row["batch"], row["position"], row["profile"]) != (str(batch), str(index), profile):
                raise ValueError((directory, batch, row))
            if not int(row["process_ns"]) > int(row["jit_ns"]) > 0 or int(row["child_peak_kib"]) <= 0:
                raise ValueError((directory, row))
    return config, rows


def summarize(evidence):
    samples = defaultdict(lambda: defaultdict(list))
    runs = {}
    prior = None
    for directory in sorted(evidence.glob("run-*")):
        config, rows = read_ledger(directory)
        keys = ("cpu", "machine", "cpu_model", "kernel", "cpu_limit", "tools",
                "executables", "sources_sha256", "lowered_ir_sha256")
        identity = [config[key] for key in keys]
        if prior is not None and prior != identity:
            raise ValueError("run identities differ")
        prior = identity
        runs[directory.name] = {
            "batches": config["batches"],
            "seed": config["seed"],
            "rows": len(rows),
            "samples_sha256": sha256((directory / "samples.csv").read_bytes()).hexdigest(),
            "throttled_delta": config["deltas"]["nr_throttled"],
        }
        for row in rows:
            for measure in MEASURES:
                samples[row["profile"]][measure].append(int(row[measure]))
    if len(runs) < 2:
        raise ValueError("two recorded runs required")
    profiles = {profile: {key: distribution(samples[profile][key]) for key in MEASURES}
                for profile in PROFILES}
    (evidence / "summary.json").write_text(json.dumps({"runs": runs, "profiles": profiles},
                                                      sort_keys=True, indent=2) + "\n")
    return profiles


def chart(evidence, profiles):
    figure, axes = plt.subplots(1, 3, figsize=(12, 3.6), layout="constrained", sharey=True)
    for axis, (measure, (scale, label)) in zip(axes, MEASURES.items(), strict=True):
        for index, profile in enumerate(PROFILES):
            row = profiles[profile][measure]
            center = row["median"] / scale
            bounds = [[(row["median"] - row["p10"]) / scale], [(row["p90"] - row["median"]) / scale]]
            axis.errorbar(center, index, xerr=bounds, fmt="o", capsize=3, color="#164a73")
        axis.set_yticks(range(len(PROFILES)), PROFILES)
        axis.set_xlabel(label)
        axis.grid(axis="x", alpha=0.25)
    axes[0].invert_yaxis()
    figure.suptitle("Checked-add fresh-process pilot — median and p10–p90")
    figure.savefig(evidence / "distributions.png", dpi=160)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, default=EVIDENCE)
    args = parser.parse_args()
    chart(args.evidence_dir, summarize(args.evidence_dir))
