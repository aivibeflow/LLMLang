"""Render the native dependent-reference transaction outcomes."""
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Ref backend | Peer write | Verify peer | Primary outcome | Peer outcome | Compatible final pair |")
print("| --- | --- | --- | --- | --- | --- |")
for row in ledger["outcomes"]:
    fields = (row["ref_backend"], row["schedule"], "yes" if row["verify_peer_in_transaction"] else "no",
              row["primary"], row["peer"], "yes" if row["after"]["compatible"] else "no")
    print("| " + " | ".join(fields) + " |")
