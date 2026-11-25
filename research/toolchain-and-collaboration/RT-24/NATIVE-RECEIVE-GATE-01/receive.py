"""Check exact Git branch candidates inside a disposable bare receive-pack."""
import json
import os
from pathlib import Path
import sys

PROTOTYPE = Path(__file__).resolve().parents[3] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))

from tests.test_rt24_merge_tree_gate import GraphImportError, InventoryError, git, import_closed, read_inventory


def checks(repo, pins):
    results = []
    for commit in sorted(set(pins)):
        tree = git(repo, "rev-parse", f"{commit}^{{tree}}").decode().strip()
        try:
            inventory = read_inventory(repo, commit)
            _, graph = import_closed(inventory)
        except (GraphImportError, InventoryError):
            result = {"commit": commit, "status": "rejected", "tree": tree}
        else:
            result = {"commit": commit, "status": "closed", "tree": inventory.tree,
                      "graph": graph.root_hash}
        results.append(result)
    return results


def receive(mode, ledger, update_args):
    updates = ([tuple(line.split()) for line in sys.stdin if line.strip()] if mode != "update" else
               [(update_args[1], update_args[2], update_args[0])])
    repo = Path.cwd()
    tips = sorted({new for _, new, ref in updates if ref.startswith("refs/heads/") and set(new) != {"0"}})
    if mode == "history" and tips:
        commits = git(repo, "rev-list", *tips, "--not", "--all").decode().splitlines()
    else:
        commits = tips
    checked = checks(repo, commits)
    with ledger.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"mode": mode, "updates": sorted(updates), "checked": checked,
                                 "quarantine": bool(os.getenv("GIT_QUARANTINE_PATH"))},
                                sort_keys=True) + "\n")
    return any(record["status"] == "rejected" for record in checked)


if __name__ == "__main__":
    sys.exit(int(receive(sys.argv[1], Path(sys.argv[2]), sys.argv[3:])))
