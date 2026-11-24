"""Render read and pack byte outcomes from the replayable native Git ledger."""
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Placement | Replacement rate | Layout | Payload blobs changed | New payload bytes | Pack plus index bytes |")
print("| --- | ---: | --- | ---: | ---: | ---: |")
for row in ledger["cases"]:
    rate = 100 * row["replacement_count"] / ledger["records"]
    print(f'| {row["placement"]} | {rate:g}% | {row["layout"]} | {row["payload_blobs_changed"]} | '
          f'{row["new_payload_blob_bytes"]:,} | {row["pack_plus_index_bytes"]:,} |')
