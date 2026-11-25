"""Inspect the exact index tree at a native Git hook in the RT-24 fixture."""
import json
from pathlib import Path
import subprocess
import sys

PROTOTYPE = Path(__file__).resolve().parents[3] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))

from tests.test_rt24_merge_tree_gate import GraphImportError, git, import_closed, read_inventory


def inspect(hook, ledger, args):
    repo = Path.cwd()
    try:
        index_tree = git(repo, "write-tree").decode().strip()
    except subprocess.CalledProcessError:
        index_tree = None
    state = "unmerged"
    if index_tree is not None:
        try:
            import_closed(read_inventory(repo, index_tree))
        except GraphImportError:
            state = "unclosed"
        else:
            state = "closed"
    result = {"hook": hook, "args": args, "index_tree": index_tree, "state": state,
              "head": git(repo, "rev-parse", "HEAD").decode().strip()}
    with ledger.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(result, sort_keys=True) + "\n")
    return state != "closed"


if __name__ == "__main__":
    sys.exit(int(inspect(sys.argv[1], Path(sys.argv[2]), sys.argv[3:])))
