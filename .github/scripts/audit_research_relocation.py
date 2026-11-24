#!/usr/bin/env python3
"""Audit path/blob changes introduced by the research reorganization."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path, PurePosixPath
import platform
import subprocess

AFTER = "fe229c3215c42d8bded531d77bbef47761ac5770"
PROPOSED = "29278112fc8559e486c651eff077e41e7b3e8b89"
MERGED = "1a5972480c22f534dd00b1c99fd57e0db089e4d5"
MANIFEST = "research/RESEARCH-CORPUS-INVENTORY-2026-11-20.json"
# Each pair retains the exact heading and the same issue number.
README_MOVES = {
    "research/RT-37-FREESTANDING-EMBEDDED-REAL-TIME/README.md": "research/RT-37/README.md",
    "research/RT-38-VERIFIED-OS-KERNELS/README.md": "research/RT-38/README.md",
}


def git(*args):
    return subprocess.check_output(["git", *args])


def research_tree(commit):
    raw = git("ls-tree", "-r", "-l", "-z", commit, "research/")
    tree = {}
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        header, name = entry.split(b"\t", 1)
        _, kind, blob, size = header.decode("ascii").split()
        name = name.decode("utf-8")
        if kind == "blob" and name != MANIFEST:
            tree[name] = (blob, int(size))
    return tree


def by_basename(paths):
    groups = defaultdict(list)
    for path in sorted(paths):
        groups[PurePosixPath(path).name].append(path)
    return groups


def relocation_map(before, after):
    removed = before.keys() - after.keys()
    added = after.keys() - before.keys()
    if not README_MOVES.keys() <= removed or not set(README_MOVES.values()) <= added:
        raise ValueError("The two scoped README moves do not match the compared trees")
    paired = dict(README_MOVES)
    basis = dict.fromkeys(paired, "explicit RT directory mapping")
    old_names = by_basename(removed - paired.keys())
    new_names = by_basename(added - set(paired.values()))
    for name in sorted(old_names.keys() & new_names.keys()):
        if len(old_names[name]) == len(new_names[name]) == 1:
            old, new = old_names[name][0], new_names[name][0]
            paired[old] = new
            basis[old] = "unique basename among unmatched paths"
    return paired, basis


def compare_inventory(manifest, tree):
    return {
        "missing": sorted(tree.keys() - manifest.keys()),
        "extra": sorted(manifest.keys() - tree.keys()),
        "stale": sorted(path for path in tree.keys() & manifest.keys() if tree[path] != manifest[path]),
    }


def audit_proposal(after, relocated_manifest):
    move_commit = git("rev-parse", f"{PROPOSED}^").decode("ascii").strip()
    if git("rev-parse", f"{move_commit}^").decode("ascii").strip() != AFTER:
        raise ValueError("Unexpected base for PR #446")
    moved_tree = research_tree(move_commit)
    proposed_tree = research_tree(PROPOSED)
    raw = git("diff", "--diff-filter=R", "--name-status", "-M100%", "-z", AFTER,
              move_commit, "--", "research/")
    fields = raw.decode("utf-8").split("\0")[:-1]
    pairs = {}
    for status, source, destination in zip(fields[::3], fields[1::3], fields[2::3], strict=True):
        if status != "R100" or after[source] != moved_tree[destination]:
            raise ValueError("The proposed move commit changed a source blob")
        pairs[source] = destination
    if set(pairs) != after.keys() - moved_tree.keys() or set(pairs.values()) != moved_tree.keys() - after.keys():
        raise ValueError("The proposed move commit did not preserve a bijection")
    remapped = {pairs.get(path, path): identity for path, identity in relocated_manifest.items()}
    if git("rev-parse", f"{MERGED}^{{tree}}") != git("rev-parse", f"{PROPOSED}^{{tree}}"):
        raise ValueError("Merged tree differs from the studied PR #446 head")
    findings = compare_inventory(remapped, proposed_tree)
    return {
        "pull_request": 446,
        "exact_move_commit": move_commit,
        "proposal_head": PROPOSED,
        "merged_commit_with_identical_tree": MERGED,
        "confirmed_exact_moves_at_intermediate_commit": len(pairs),
        "artifacts_at_proposal_head": len(proposed_tree),
        "additional_artifacts_at_proposal_head": sorted(proposed_tree.keys() - moved_tree.keys()),
        "removed_artifacts_at_proposal_head": sorted(moved_tree.keys() - proposed_tree.keys()),
        "changed_at_proposal_head": sum(
            moved_tree[path] != proposed_tree[path] for path in moved_tree.keys() & proposed_tree.keys()
        ),
        "inventory_differences_after_both_remaps": findings,
    }


def audit():
    parent = git("rev-parse", f"{AFTER}^").decode("ascii").strip()
    before, after = research_tree(parent), research_tree(AFTER)
    records = json.loads(git("show", f"{AFTER}:{MANIFEST}"))["artifacts"]
    manifest = {record["path"]: (record["git_blob_sha"], record["size_bytes"]) for record in records}
    if len(manifest) != len(records):
        raise ValueError("Inventory has duplicate paths")

    moves, basis = relocation_map(before, after)
    common = before.keys() & after.keys()
    relocated_manifest = {moves.get(path, path): identity for path, identity in manifest.items()}
    if len(relocated_manifest) != len(manifest):
        raise ValueError("Relocation would merge inventory records")

    inventory = {
        "pre_move": compare_inventory(manifest, before),
        "post_move_by_path": compare_inventory(manifest, after),
        "post_move_after_remap": compare_inventory(relocated_manifest, after),
    }
    all_pairs = {**{path: path for path in common}, **moves}
    modified = [
        {
            "old_path": source,
            "new_path": all_pairs[source],
            "old_blob": before[source][0],
            "new_blob": after[all_pairs[source]][0],
            "old_size": before[source][1],
            "new_size": after[all_pairs[source]][1],
        }
        for source in sorted(all_pairs) if before[source] != after[all_pairs[source]]
    ]
    moved = [
        {"old_path": old, "new_path": new, "mapping_basis": basis[old],
         "same_blob": before[old] == after[new]}
        for old, new in sorted(moves.items())
    ]
    unmatched_added = sorted(after.keys() - common - set(moves.values()))
    unmatched_removed = sorted(before.keys() - common - moves.keys())
    return {
        "schema": "rt00-inventory-relocation-v1",
        "pre_move_commit": parent,
        "post_move_commit": AFTER,
        "manifest_blob_at_post_move": git("rev-parse", f"{AFTER}:{MANIFEST}").decode("ascii").strip(),
        "environment": {
            "python": platform.python_version(),
            "git": git("--version").decode("ascii").strip(),
            "kernel": platform.release(),
            "arch": platform.machine(),
        },
        "summary": {
            "manifest_records": len(manifest),
            "pre_move_artifacts": len(before),
            "post_move_artifacts": len(after),
            "move_basis_counts": dict(Counter(entry["mapping_basis"] for entry in moved)),
            "move_same_bytes": sum(entry["same_blob"] for entry in moved),
            "move_changed_bytes": sum(not entry["same_blob"] for entry in moved),
            "same_path_changed_bytes": sum(before[path] != after[path] for path in common),
            "inventory": {
                name: {kind: len(paths) for kind, paths in findings.items()}
                for name, findings in inventory.items()
            },
        },
        "unmatched_added": unmatched_added,
        "unmatched_removed": unmatched_removed,
        "moves": moved,
        "modified_pairs": modified,
        "inventory_differences": inventory,
        "second_migration": audit_proposal(after, relocated_manifest),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
