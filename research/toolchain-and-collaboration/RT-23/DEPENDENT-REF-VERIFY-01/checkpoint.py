"""Expose a deterministic native reference-transaction prepared checkpoint."""
import json
import os
from pathlib import Path
import sys
import time

work = Path(sys.argv[1])
phase = sys.argv[2]
if phase == "prepared" and os.environ.get("RT23_ACTOR") == "primary":
    values = [line.split() for line in sys.stdin]
    complete = work / "checkpoint.next"
    complete.write_text(json.dumps(values) + "\n", encoding="utf-8")
    complete.rename(work / "checkpoint.json")
    expiry = time.monotonic() + 15
    while not (work / "release").exists():
        if time.monotonic() >= expiry:
            raise TimeoutError("reference transaction did not receive its release")
        time.sleep(0.01)
