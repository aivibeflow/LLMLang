"""Render chunk reuse and actual Git pack sizes from the native replay ledger."""
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Edit | Boundary | Reused / original chunks | New chunk bytes | Pack + index bytes |")
print("| --- | --- | ---: | ---: | ---: |")
for edit, layouts in ledger["cases"].items():
    for layout, row in layouts.items():
        reuse = f'{row["reused_chunks"]}/{row["before_chunks"]}'
        print(f'| {edit} | {layout} | {reuse} | {row["new_chunk_bytes"]:,} | {row["pack_plus_index_bytes"]:,} |')
