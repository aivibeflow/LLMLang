"""Render query dispositions, receipt reads and Git object sizes."""

import json
from pathlib import Path

LABELS = {
    "prepared_objects_before_cas": "Before journal CAS",
    "same_request_after_cas": "After journal CAS",
    "oldest": "Oldest request",
    "same_key_other_scope": "Same request key in another scope",
    "middle": "Middle of history",
    "recent": "Second newest request",
    "latest": "Newest request",
    "same_key_different_commit": "Same key and tree, different commit",
    "absent_key": "Absent request",
    "future_key_at_pinned_head": "Later request at the pinned prefix",
    "old_key_at_pinned_head": "Old request at the pinned prefix",
}


def main():
    data = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))["results"]
    print("| Query | Full scan | Eight-entry scan | Indexed tree |")
    print("|---|---|---|---|")
    for row in data["cas_boundary"] + data["queries"]:
        cells = ["`" + result["result"] + "` / " + str(result["receipts_examined"])
                 for result in row["observations"].values()]
        print("| " + " | ".join([LABELS[row["case"]], *cells]) + " |")
    print()
    print("| Git object type | Full scan objects | Indexed objects | Full scan bytes | Indexed bytes |")
    print("|---|---:|---:|---:|---:|")
    objects = data["reachable_objects"]
    for kind in ("commit", "tree", "blob"):
        linear = objects["scan"][kind]
        indexed = objects["indexed"][kind]
        print(f"| {kind} | {linear['objects']:,} | {indexed['objects']:,} | "
              f"{linear['uncompressed_bytes']:,} | {indexed['uncompressed_bytes']:,} |")


if __name__ == "__main__":
    main()
