"""Generate the report's coroutine CPU comparison from the retained sample."""

import argparse
import json
from pathlib import Path


def chart(sample):
    normal = sample["normal"]
    totals = [normal["thread_cpu_ns"], sum(normal["profiled"].values()), sum(normal["spanning"].values())]
    milliseconds = [round(value / 1_000_000) for value in totals]
    return "\n".join((
        "xychart-beta",
        '    title "One asyncio execution on one native thread"',
        '    x-axis ["Thread total", "Dispatch charges", "Spanning charges"]',
        '    y-axis "CPU milliseconds" 0 --> 180',
        f"    bar {milliseconds}",
    ))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sample", type=Path)
    options = parser.parse_args()
    print(chart(json.loads(options.sample.read_text())))
