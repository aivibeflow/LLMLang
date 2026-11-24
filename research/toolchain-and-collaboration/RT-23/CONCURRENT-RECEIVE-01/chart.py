"""Render controlled concurrency outcomes from the saved Git receive trace."""
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Lock scope | Both via wrapper | Atomic requested | Batch | Git exit by actor | Final compatibility |")
print("| --- | --- | --- | --- | --- | --- |")
for row in ledger["results"]:
    actual = ", ".join(f"{actor} {status}" for actor, status in row["push_exit"].items())
    fields = (row["policy"], "yes" if row["peer_uses_wrapper"] else "no",
              "yes" if row["atomic_requested"] else "no", "joint" if row["paired_update"] else "separate",
              actual, "compatible" if row["after"]["compatible"] else "incompatible")
    print("| " + " | ".join(fields) + " |")
