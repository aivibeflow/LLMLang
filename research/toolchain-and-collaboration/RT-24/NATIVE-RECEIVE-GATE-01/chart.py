"""Render commit admission and reachability from the native Git evidence."""
import json
from pathlib import Path

ledger = json.loads(Path(__file__).with_name("evidence.json").read_text(encoding="utf-8"))

def yesno(flag):
    return "yes" if flag else "no"

print("| Gate | Push | Atomic | Unclosed history already present | Exit | Unclosed commit reachable |")
print("| --- | --- | --- | --- | ---: | --- |")
for row in ledger["results"]:
    fields = (row["mode"], row["request"], yesno(row["atomic"]), yesno(row["preexisting_unclosed"]),
              row["push_status"], yesno(row["unclosed_commit_reachable"]))
    print("| " + " | ".join(map(str, fields)) + " |")
