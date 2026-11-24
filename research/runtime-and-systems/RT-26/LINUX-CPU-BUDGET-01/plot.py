"""Generate the exact CPU comparison chart from one retained sample."""

import argparse
import json
from pathlib import Path


def chart(sample, evidence):
    group = sample["locally_admitted_pair"]
    milliseconds = [round(row["cpu_us"] / 1_000) for row in group["workers"]]
    milliseconds.append(round(group["wait4_cpu_sum_us"] / 1_000))
    limit = evidence["comparison_group_limit_us"] // 1_000
    return "\n".join((
        "xychart-beta",
        '    title "CPU charged at reaping"',
        '    x-axis ["Worker 1", "Worker 2", "Both workers"]',
        '    y-axis "CPU milliseconds" 0 --> 1300',
        f"    bar {milliseconds}",
        f"    line {[limit] * len(milliseconds)}",
    ))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sample", type=Path)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    print(chart(json.loads(args.sample.read_text()), json.loads(args.evidence.read_text())))
