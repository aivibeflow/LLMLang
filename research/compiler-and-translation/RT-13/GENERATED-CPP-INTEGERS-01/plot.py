"""Generate the report's code and object size chart from the retained evidence."""

import argparse
import json
from pathlib import Path

PROFILES = (("gxx_O0", "GCC O0"), ("gxx_O3", "GCC O3"),
            ("clangxx_O0", "Clang O0"), ("clangxx_O3", "Clang O3"))


def chart(evidence):
    result = evidence["profiles"]
    labels = [label for _, label in PROFILES]
    objects = [result[profile]["object_bytes"] for profile, _ in PROFILES]
    extents = [result[profile]["exported_extent_sum_bytes"] for profile, _ in PROFILES]
    return "\n".join((
        "xychart-beta",
        '    title "C++ integer probe artifact sizes"',
        f"    x-axis {json.dumps(labels)}",
        '    y-axis "Bytes" 0 --> 16000',
        f"    bar {objects}",
        f"    line {extents}",
    ))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    options = parser.parse_args()
    print(chart(json.loads(options.evidence.read_text())))
