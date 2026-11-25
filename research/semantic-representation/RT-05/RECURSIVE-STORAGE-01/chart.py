"""Render the largest group's physical storage and read costs."""

import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))
groups = {row["variant"]: row["layouts"] for row in ledger["groups"] if row["size"] == 256}
layouts = ("whole", "flat", "blocked")
print("| Metric at 256 members | Whole | Flat | Blocked |")
print("| --- | ---: | ---: | ---: |")
rows = (
    ("Base stored objects", ("base", "stored_objects")),
    ("Full admission, bytes", ("base", "full_admission_bytes")),
    ("Admitted one-step read, bytes", ("base", "post_admission_read_bytes", "entry0/fuel1")),
    ("Admitted full-cycle read, bytes", ("base", "post_admission_read_bytes", "entry0/fuel257")),
    ("Display rename, new bytes", ("display_rename", "new_bytes")),
    ("One body edit, new bytes", ("body_edit", "new_bytes")),
    ("Exact provider edit, new bytes", ("provider_edit", "new_bytes")),
    ("Slot rotation, new bytes", ("slot_rotate", "new_bytes")),
)
for label, (variant, measure, *detail) in rows:
    values = [groups[variant][layout][measure] for layout in layouts]
    if detail:
        values = [value[detail[0]] for value in values]
    print(f"| {label} | " + " | ".join(f"{value:,}" for value in values) + " |")
