"""Render the shared workload and distinct binding outcomes."""
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Transfer | Rows per provider and target | Changed language traces | Changed descriptor audits | Changed combined rows |")
print("| --- | ---: | ---: | ---: | ---: |")
for timing in ("before_cleanup", "after_cleanup"):
    row = ledger["results"][f"{timing}/rebind"]
    total, traces, audits = (row["total_rows_per_provider"], row["language_trace_changes"],
                             row["physical_audit_changes"])
    changed = row["incorrect_cached_rows_with_caller_and_contract_key"]
    print(f"| {timing} | {total:,} | {traces:,} | {audits:,} | {changed:,} |")
