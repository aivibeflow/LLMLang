"""Render the driver and signed cancellation case comparison."""
import json
from pathlib import Path

data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
print("| Version and profile | Plain differences, values / flags | Literal constrained differences, values / flags | Downward forced inline | Downward retained call |")
print("| --- | ---: | ---: | --- | --- |")
for profile, row in data["profiles"].items():
    plain, strict = row["counts"]["plain"], row["counts"]["strict"]
    bits = row["inlining"]["bits"]
    inline = "+0" if bits["downward/forced_inline"] == "0000000000000000" else "-0"
    retained = "-0" if bits["downward/retained_call"] == "8000000000000000" else "+0"
    print(f'| {profile} | {plain["value_mismatches"]} / {plain["flag_mismatches"]} | '
          f'{strict["value_mismatches"]} / {strict["flag_mismatches"]} | {inline} | {retained} |')
