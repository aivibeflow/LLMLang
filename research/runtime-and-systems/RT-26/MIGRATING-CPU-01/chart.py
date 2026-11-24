"""Render the saved native CPU sample with durations in milliseconds."""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--sample", type=Path, default=HERE / "sample.json")
config = parser.parse_args()
record = json.loads(config.sample.read_text(encoding="utf-8"))["O3"]
print("| Case | Task dispatch sum (ms) | Peer (ms) | Origin span (ms) | Cross-clock subtraction (ms) | Process (ms) |")
print("| --- | ---: | ---: | ---: | ---: | ---: |")
for case, row in record.items():
    quantities = (row["first_task_ns"] + row["second_task_ns"], row["peer_ns"],
                  row["origin_span_ns"], row["cross_worker_subtraction_ns"], row["process_ns"])
    print("| " + " | ".join([case, *(f"{ns / 1_000_000:.1f}" for ns in quantities)]) + " |")
