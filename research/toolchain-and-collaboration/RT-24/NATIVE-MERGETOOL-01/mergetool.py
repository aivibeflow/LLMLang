"""Repository-context adapter for one conflicted file in the RT-24 fixture."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

PROTOTYPE = Path(__file__).resolve().parents[3] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))

from src.semantic_graph import canonical_bytes
from tests.test_rt24_merge_tree_gate import MANIFEST, import_closed, read_inventory
from tests.test_rt24_semantic_merge_core import merge_inventories


class Unsupported(ValueError):
    pass


def git(*args, data=None, index=None):
    environment = dict(os.environ)
    if index is not None:
        environment["GIT_INDEX_FILE"] = str(index)
    return subprocess.run(
        ["git", *args], env=environment, input=data, capture_output=True, check=True, timeout=30,
    ).stdout


def stage_entries():
    entries = {}
    for entry in git("ls-files", "-u", "-z").split(b"\0")[:-1]:
        info, raw_path = entry.split(b"\t", 1)
        mode, oid, stage = info.decode("ascii").split()
        entries.setdefault(os.fsdecode(raw_path), {})[int(stage)] = (mode, oid)
    return entries


def resolve(path, side_files):
    if not path.startswith("program/") or path == MANIFEST:
        raise Unsupported("outside-fixture-source")
    index_path = Path(os.fsdecode(git("rev-parse", "--git-path", "index").strip()))
    index_bytes = index_path.read_bytes()
    unmerged = stage_entries()
    if set(unmerged.get(path, {})) != {1, 2, 3}:
        raise Unsupported("three-file-stages-required")
    if sorted(key for key in unmerged if key.startswith("program/")) != [path]:
        raise Unsupported("multiple-semantic-conflicts")

    current = git("rev-parse", "--verify", "HEAD").decode().strip()
    merge_heads = Path(os.fsdecode(git("rev-parse", "--git-path", "MERGE_HEAD").strip()))
    if not merge_heads.is_file():
        raise Unsupported("single-merge-required")
    incoming = merge_heads.read_text(encoding="ascii").splitlines()
    if len(incoming) != 1:
        raise Unsupported("single-merge-required")
    theirs = incoming[0]
    bases = git("merge-base", "--all", current, theirs).decode().splitlines()
    if len(bases) != 1:
        raise Unsupported("single-base-required")
    revisions = (bases[0], current, theirs)

    for stage, (revision, temp_file) in enumerate(zip(revisions, side_files, strict=True), 1):
        mode, staged_oid = unmerged[path][stage]
        committed_oid = git("rev-parse", "--verify", f"{revision}:{path}").decode().strip()
        supplied_oid = git("hash-object", "--stdin", data=temp_file.read_bytes()).decode().strip()
        if mode != "100644" or not committed_oid == staged_oid == supplied_oid:
            raise Unsupported("input-stage-mismatch")

    repo = Path.cwd()
    inputs = [read_inventory(repo, rev) for rev in revisions]
    merged = merge_inventories(*inputs)
    if merged.status != "structural-candidate":
        detail = ",".join(f"{item.kind}/{item.slot}" for item in merged.conflicts)
        raise Unsupported(f"{merged.status} {detail}".strip())

    # Preserve this fixture's physical layout by collecting all slots occurring at this path.
    candidates = {
        item["slot"] for source in side_files for item in json.loads(source.read_bytes())
    }
    rows = [item for item in json.loads(merged.export) if item["slot"] in candidates]
    replacement = canonical_bytes(rows) + b"\n"
    with TemporaryDirectory(prefix="rt24-private-index-") as directory:
        private_index = Path(directory) / "index"
        private_index.write_bytes(index_bytes)
        blob = git("hash-object", "-w", "--stdin", data=replacement).decode().strip()
        git("update-index", "--add", "--cacheinfo", "100644", blob, path, index=private_index)
        for ordinary in sorted(unmerged.keys() - {path}):
            git("update-index", "--force-remove", "--", ordinary, index=private_index)
        tree = git("write-tree", index=private_index).decode().strip()
        _, actual = import_closed(read_inventory(repo, tree))
        if actual.selections != merged.selections:
            raise Unsupported("staged-semantic-candidate-differs")

    if index_path.read_bytes() != index_bytes or git("rev-parse", "--verify", "HEAD").decode().strip() != current:
        raise Unsupported("merge-state-changed")
    if merge_heads.read_text(encoding="ascii").splitlines() != incoming:
        raise Unsupported("merge-state-changed")
    return replacement


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("local", type=Path)
    parser.add_argument("remote", type=Path)
    parser.add_argument("merged", type=Path)
    args = parser.parse_args()
    try:
        merged = Path(os.path.abspath(args.merged))
        if merged.is_symlink() or not merged.is_file():
            raise Unsupported("regular-merged-file-required")
        path = merged.relative_to(Path.cwd()).as_posix()
        replacement = resolve(path, (args.base, args.local, args.remote))
        merged.write_bytes(replacement)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"RT24 MERGETOOL STOP {error}", file=sys.stderr)
        return 1
    print("RT24 MERGETOOL OK structural-candidate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
