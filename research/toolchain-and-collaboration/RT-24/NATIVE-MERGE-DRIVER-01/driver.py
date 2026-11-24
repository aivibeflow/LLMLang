"""Probe native Git driver inputs and implement a fixture-local merge policy."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

PROTOTYPE = Path(__file__).resolve().parents[3] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))

from src.semantic_graph import canonical_bytes, digest
from tests.test_rt24_semantic_merge_core import resolve_slot


def git(*args, data=None):
    return subprocess.run(["git", *args], input=data, check=True, capture_output=True, timeout=20).stdout


def rows(data):
    items = json.loads(data)
    result = {value["slot"]: value for value in items}
    if len(result) != len(items):
        raise ValueError("duplicate slot")
    return result


def local_candidate(sides):
    values = [rows(data) for data in sides]
    result = []
    for slot in sorted(set().union(*values)):
        choices = [side.get(slot) for side in values]
        addresses = [None if choice is None else digest(choice) for choice in choices]
        selected, conflict = resolve_slot(slot, *addresses)
        if conflict is not None:
            return None
        if selected is not None:
            result.append(choices[addresses.index(selected)])
    return canonical_bytes(result) + b"\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy", choices=("local-slots", "require-context"))
    parser.add_argument("ledger", type=Path)
    parser.add_argument("base", type=Path)
    parser.add_argument("ours", type=Path)
    parser.add_argument("theirs", type=Path)
    parser.add_argument("marker_size", type=int)
    parser.add_argument("path")
    args = parser.parse_args()
    sides = [temp.read_bytes() for temp in (args.base, args.ours, args.theirs)]
    protocol_files = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REBASE_HEAD", "rebase-merge", "rebase-apply")
    observed = {name: Path(os.fsdecode(git("rev-parse", "--git-path", name).strip())).exists()
                for name in protocol_files}
    with args.ledger.open("a", encoding="utf-8") as stream:
        record = {
            "path": args.path, "marker_size": args.marker_size,
            "blobs": [git("hash-object", "--stdin", data=side).decode().strip() for side in sides],
            "head": git("rev-parse", "--verify", "HEAD").decode().strip(),
            "protocol_files": observed,
            "unmerged_entries": len(git("ls-files", "-u", "-z").split(b"\0")) - 1,
            "index_caller": git("rev-parse", ":program/caller.json").decode().strip(),
        }
        stream.write(json.dumps(record, sort_keys=True) + "\n")

    if args.policy == "require-context":
        print("RT24 merge driver requires explicit repository context", file=sys.stderr)
        return 1
    candidate = local_candidate(sides)
    if candidate is None:
        return 1
    args.ours.write_bytes(candidate)
    return 0


if __name__ == "__main__":
    sys.exit(main())
