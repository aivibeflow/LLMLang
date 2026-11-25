"""Check the archived measurement matrix and plot medians with observed ranges."""
import argparse
import csv
from itertools import product
from pathlib import Path
from statistics import median

from measure import SHAPES, SIZES


def read_samples(path, repeats):
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    trials = sorted({int(row["trial"]) for row in rows})
    assert trials == list(range(1, repeats + 1))
    assert len(rows) == len(trials) * len(SHAPES) * len(SIZES)
    counts = {}
    seen = set()
    orders = set()
    for row in rows:
        trial = int(row["trial"])
        order = int(row["order"])
        size = int(row["objects"])
        shape = row["shape"]
        assert row["verified"] == "True"
        key = (trial, shape, size)
        assert key not in seen and (trial, order) not in orders
        seen.add(key)
        orders.add((trial, order))
        fields = ("dependency_edges", "manifest_bytes", "archive_bytes")
        values = tuple(int(row[field]) for field in fields)
        assert values == counts.setdefault((shape, size), values)
        expected_edges = {
            "chain": size - 1,
            "fanout": size - 1,
            "diamond": 5 * (size // 4) - 1,
            "many-dependencies": 16 * size - 136,
        }
        assert values[0] == expected_edges[shape]
    assert seen == set(product(trials, SHAPES, SIZES))
    assert orders == set(product(trials, range(1, len(SHAPES) * len(SIZES) + 1)))
    return rows


def ranges(rows, shape, field):
    groups = []
    for size in SIZES:
        values = [float(row[field]) for row in rows
                  if row["shape"] == shape and int(row["objects"]) == size]
        groups.append((min(values), median(values), max(values)))
    return groups


def plot(rows, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["svg.hashsalt"] = "llmlang-provider-333"
    fields = (
        ("provider_build_seconds", "Build (s)", 1),
        ("archive_verification_seconds", "Verification (s)", 1),
        ("process_peak_rss_bytes", "Process peak RSS (MiB)", 1024**2),
        ("peak_provider_tempdir_bytes", "Temp bytes at cleanup (MiB)", 1024**2),
    )
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.2), layout="constrained")
    for axis, (field, label, divisor) in zip(axes.flat, fields):
        for shape, marker in zip(SHAPES, ("o", "s", "^", "D")):
            bounds = ranges(rows, shape, field)
            centers = [middle / divisor for _, middle, _ in bounds]
            errors = [
                [(middle - lower) / divisor for lower, middle, _ in bounds],
                [(upper - middle) / divisor for _, middle, upper in bounds],
            ]
            axis.errorbar(SIZES, centers, yerr=errors, marker=marker, capsize=3,
                          alpha=0.86, label=shape)
        axis.set(xscale="log", yscale="log", xlabel="Objects", ylabel=label)
        axis.set_xticks(SIZES, [f"{value:,}" for value in SIZES])
        axis.grid(axis="y", alpha=0.25)
    axes[0, 0].legend(loc="upper left", framealpha=0.95)
    fig.suptitle("Provider archive workload, median and observed range")
    fig.savefig(output, metadata={"Date": None} if output.suffix == ".svg" else None)
    if output.suffix == ".svg":
        lines = output.read_text(encoding="utf-8").splitlines()
        output.write_text("\n".join(line.rstrip() for line in lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("samples", type=Path)
    parser.add_argument("--plot", type=Path)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    rows = read_samples(args.samples, args.repeats)
    print(f"Verified {len(rows)} measurements with stable edge and byte counts.")
    for shape in SHAPES:
        for size, (low, center, high) in zip(SIZES, ranges(rows, shape, "provider_build_seconds")):
            print(f"{shape:18} {size:>5}  {center:7.3f} s  [{low:.3f}, {high:.3f}]")
    if args.plot:
        plot(rows, args.plot)


if __name__ == "__main__":
    main()
