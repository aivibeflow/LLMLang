"""Generate the report's Mermaid chart from the exact Linux mapping ledger."""

import argparse
import json
from pathlib import Path


STAGES = ("prefault", "two_readers", "after_half_written", "after_child_exit")


def chart(ledger):
    cases = ledger["cases"]
    rss = [cases["shared"][stage]["rss_kib"] for stage in STAGES]
    if rss != [cases["private"][stage]["rss_kib"] for stage in STAGES]:
        raise ValueError("The chart assumes the two RSS series coincide")
    shared_pss = [cases["shared"][stage]["pss_kib"] for stage in STAGES]
    private_pss = [cases["private"][stage]["pss_kib"] for stage in STAGES]
    return "\n".join((
        "xychart-beta",
        '    title "Resident and proportional memory by phase"',
        '    x-axis ["Parent only", "Two readers", "After writes", "Child exited"]',
        '    y-axis "KiB" 0 --> 4096',
        f"    bar {rss}",
        f"    line {shared_pss}",
        f"    line {private_pss}",
    ))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args()
    print(chart(json.loads(args.ledger.read_text())))
