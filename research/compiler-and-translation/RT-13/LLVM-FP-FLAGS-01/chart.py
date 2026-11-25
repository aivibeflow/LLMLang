"""Render verifier-admitted LLVM floating-point flag differences."""
import json
from pathlib import Path

data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Pipeline | Rows | Contract differences | Signed-zero differences under nsz | NaN inputs excluded for nnan |")
print("| --- | ---: | ---: | ---: | ---: |")
for name, profile in data["profiles"].items():
    rows = profile["rows"]
    contract = profile["contract_differences_from_split"]
    zero = profile["nsz_differences_from_signed_zero"]
    excluded = profile["nnan_inputs_excluded"]
    print(f"| {name} | {rows:,} | {contract:,} | {zero:,} | {excluded:,} |")
