#!/usr/bin/env python3
"""Build each declared Lean library root separately and stop at the first failure.

Lake's --fail-fast option is not available in the pinned Lean/Lake 4.34.0
toolchain. Building roots one at a time prevents Lake from scheduling every
independent library root before an early root failure is reported.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


LAKEFILE = Path(__file__).with_name("lakefile.lean")


def main() -> int:
    source = LAKEFILE.read_text(encoding="utf-8")
    match = re.search(r"lean_lib\s+\w+\s+where(?P<body>.*?)(?=\n\S|\Z)", source, re.S)
    if match is None:
        print(f"Could not find lean_lib roots in {LAKEFILE}", file=sys.stderr)
        return 2

    roots_match = re.search(r"roots\s*:=\s*#\[(?P<roots>.*?)\]", match.group("body"), re.S)
    if roots_match is None:
        print(f"Could not find the lean_lib roots list in {LAKEFILE}", file=sys.stderr)
        return 2

    roots = re.findall(r"`([A-Za-z_][A-Za-z0-9_.]*)", roots_match.group("roots"))
    if not roots:
        print(f"No Lean library roots found in {LAKEFILE}", file=sys.stderr)
        return 2

    for root in roots:
        print(f"::group::Build Lean root {root}", flush=True)
        result = subprocess.run(["lake", "build", f"+{root}"], check=False)
        print("::endgroup::", flush=True)
        if result.returncode != 0:
            print(
                f"Stopping after the first failed Lean root: {root} "
                f"(exit code {result.returncode})",
                file=sys.stderr,
                flush=True,
            )
            return result.returncode

    print(f"Successfully built all {len(roots)} Lean library roots.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
