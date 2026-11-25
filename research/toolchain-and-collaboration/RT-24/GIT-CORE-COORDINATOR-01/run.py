"""Connect the closed merge core to explicit native Git operands and ref updates."""
import argparse
from dataclasses import asdict, dataclass
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
GRAPH = HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
NATIVE = HERE.parents[1] / "RT-20" / "EXACT-TREE-ACCEPTANCE-01" / "run.py"
sys.path.insert(0, str(GRAPH))

from src.semantic_dependency_index import SemanticObjectError, publish_declaration
from src.semantic_graph import ContentStore, canonical_bytes, make_snapshot
from src.semantic_merge_core import merge_closed, pin_merge_input
from tests.test_candidate_graph_audit import declaration
from tests.test_rt24_merge_tree_gate import (
    GraphImportError, InventoryError, import_closed, manifest, publish_rows, read_inventory, row,
)

spec = spec_from_file_location("rt24_pinned_native_git", NATIVE)
native = module_from_spec(spec)
sys.modules[spec.name] = native
spec.loader.exec_module(native)
GIT = native.git
HEAD = native.HEAD
STATE = "program/state.json"
MODES = ("merge", "rebase", "cherry-pick")


@dataclass(frozen=True)
class Request:
    operation: str
    base: str
    ours: str
    theirs: str


def tree(repo, declarations, incomplete=False, outside_source=False):
    files = {"manifest.json": manifest(STATE, "program/absent.json") if incomplete else manifest(STATE),
             "state.json": [row(slot, value) for slot, value in sorted(declarations.items())]}
    staged = []
    for name, value in sorted(files.items()):
        address = GIT(repo, "hash-object", "-w", "--stdin", payload=canonical_bytes(value).decode() + "\n")
        staged.append(f"100644 blob {address}\t{name}\n")
    program = GIT(repo, "mktree", payload="".join(staged))
    entries = f"040000 tree {program}\tprogram\n"
    if outside_source:
        outside = GIT(repo, "hash-object", "-w", "--stdin", payload="outside declared source scope\n")
        entries += f"100644 blob {outside}\tREADME.md\n"
    return GIT(repo, "mktree", payload=entries)


def object_commit(repo, content, message, parents=()):
    return GIT(repo, "commit-tree", content, *(flag for parent in parents for flag in ("-p", parent)),
               payload=message + "\n")


def exact_parents(repo, commit):
    return tuple(GIT(repo, "show", "-s", "--format=%P", commit).split())


def role_check(repo, request):
    if request.operation not in MODES:
        return None
    if any(re.fullmatch(r"[0-9a-f]{40}", value) is None for value in
           (request.base, request.ours, request.theirs)):
        return None
    for value in (request.base, request.ours, request.theirs):
        resolved = GIT(repo, "rev-parse", "--verify", f"{value}^{{commit}}", check=False)
        if resolved.returncode or resolved.stdout.strip() != value:
            return None
    if request.operation == "merge":
        ancestry = GIT(repo, "merge-base", "--all", request.ours, request.theirs, check=False)
        if ancestry.returncode or ancestry.stdout.split() != [request.base]:
            return None
        return request.ours, (request.ours, request.theirs)
    if exact_parents(repo, request.theirs) != (request.base,):
        return None
    expected_head = request.theirs if request.operation == "rebase" else request.ours
    return expected_head, (request.ours,)


def coordinate(repo, request, after_validation=lambda: None):
    roles = role_check(repo, request)
    if roles is None:
        return {"status": "wrong-base-or-operation"}
    expected_head, parents = roles
    if native.lookup(repo, HEAD) != expected_head:
        return {"status": "stale-head"}
    store = ContentStore()
    snapshots = []
    source_trees = []
    try:
        for commit in (request.base, request.ours, request.theirs):
            if GIT(repo, "ls-tree", "--name-only", commit).splitlines() != ["program"]:
                return {"status": "unsupported-tree"}
            inventory = read_inventory(repo, commit)
            _, fresh = import_closed(inventory)
            if publish_rows(inventory.declarations, store) != fresh:
                return {"status": "unreproducible-source"}
            snapshots.append(pin_merge_input(fresh, {}))
            source_trees.append(inventory.tree)
    except (GraphImportError, InventoryError, SemanticObjectError):
        return {"status": "invalid-inventory"}
    merged = merge_closed(store, *snapshots)
    if merged.candidate is None:
        return {"status": "semantic-conflict", "kinds": [entry.kind for entry in merged.conflicts]}

    candidate = merged.candidate.snapshot
    selected = {slot: store.get(address).payload for slot, address in candidate.selections}
    exact_tree = tree(repo, selected)
    _, rebuilt = import_closed(read_inventory(repo, exact_tree))
    rebuilt = make_snapshot(rebuilt.mapping, candidate.parent_roots)
    if rebuilt != candidate:
        return {"status": "unreproducible-candidate"}
    after_validation()
    child = object_commit(repo, exact_tree, f"checked semantic {request.operation}", parents)
    update = GIT(repo, "update-ref", HEAD, child, expected_head, check=False)
    if update.returncode:
        current = native.lookup(repo, HEAD)
        return {"status": "stale-head" if current != expected_head else "ref-update-failed"}
    assert GIT(repo, "rev-parse", f"{child}^{{tree}}") == exact_tree
    assert exact_parents(repo, child) == parents
    return {"status": "published", "source_trees": source_trees, "candidate_tree": exact_tree,
            "candidate_root": candidate.root_hash, "commit": child, "parents": parents}


def graphs(case):
    x = declaration("contract", "x", {"value": 0})
    y = declaration("contract", "y", {"value": 0})
    original = {"x": x, "y": y}
    if case == "same-slot":
        return original, dict(original, x={**x, "content": {"value": 1}}), dict(
            original, x={**x, "content": {"value": 2}}
        )
    if case == "dangling-dependency":
        store = ContentStore()
        contract = publish_declaration(store, x)
        ref = [{"reference_id": "provided", "relation": "provides_contract",
                "target_hash": contract, "target_kind": "contract"}]
        leaf = declaration("function", "leaf", {"value": 1}, references=ref)
        exact = publish_declaration(store, leaf)
        caller = declaration("function", "caller", {}, references=ref, call_sites=[
            {"call_site_id": "direct", "targets": [
                {"target_id": "target", "target_hash": exact, "condition": None,
                 "required_contract_hash": contract},
            ]},
        ])
        start = {"x": x, "y": y, "leaf": leaf}
        return start, dict(start, leaf={**leaf, "content": {"value": 2}}), dict(start, caller=caller)
    return original, dict(original, x={**x, "content": {"value": 1}}), dict(
        original, y={**y, "content": {"value": 2}}
    )


def prepare(repo, mode, case):
    repo.mkdir()
    GIT(repo, "init", "--quiet", "--template=", "--object-format=sha1", "--initial-branch=research/all")
    base, ours, theirs = graphs(case)
    old = object_commit(repo, tree(repo, base), "common base")
    left = object_commit(repo, tree(repo, ours), "left edit", (old,))
    right_tree = tree(repo, theirs, incomplete=case == "missing-source",
                      outside_source=case == "outside-source")
    right = object_commit(repo, right_tree, "right edit", (old,))
    current = right if mode == "rebase" else left
    GIT(repo, "update-ref", HEAD, current)
    GIT(repo, "read-tree", "--reset", "-u", current)
    return Request(mode, old, left, right), current


def native_control(repo, mode):
    request, _ = prepare(repo, mode, "independent")
    if mode == "merge":
        command = ("merge", "--no-commit", request.theirs)
    elif mode == "rebase":
        command = ("rebase", "--onto", request.ours, request.base)
    else:
        command = ("cherry-pick", "--no-commit", request.theirs)
    result = GIT(repo, *command, check=False)
    conflicts = GIT(repo, "diff", "--name-only", "--diff-filter=U").splitlines()
    assert result.returncode != 0 and conflicts == [STATE], (mode, result.stdout, result.stderr)
    return conflicts


def check(root):
    results = []
    for mode in MODES:
        cases = ("independent", "same-slot", "dangling-dependency", "missing-source",
                 "outside-source", "wrong-base", "absent-commit", "head-race")
        for case in cases:
            repo = root / f"{mode}-{case}"
            request, original = prepare(repo, mode, case)
            if case == "wrong-base":
                request = Request(mode, request.ours, request.ours, request.theirs)
            if case == "absent-commit":
                request = Request(mode, request.base, request.ours, "0" * 40)
            if case == "independent":
                (repo / STATE).write_text("uncommitted worktree bytes\n")
            before_index = (repo / ".git" / "index").read_bytes()

            def move_head():
                other_tree = GIT(repo, "rev-parse", f"{original}^{{tree}}")
                replacement = object_commit(repo, other_tree, "unrelated native update", (original,))
                GIT(repo, "update-ref", HEAD, replacement, original)

            result = coordinate(repo, request, move_head if case == "head-race" else lambda: None)
            current = native.lookup(repo, HEAD)
            assert (repo / ".git" / "index").read_bytes() == before_index
            if case == "independent":
                assert (repo / STATE).read_text() == "uncommitted worktree bytes\n"
                assert result["status"] == "published" and result["commit"] == current
                _, reopened = import_closed(read_inventory(repo, current))
                assert set(reopened.mapping) == {"x", "y"}
                payload = read_inventory(repo, current).declarations
                assert [payload[key]["content"]["value"] for key in ("x", "y")] == [1, 2]
            elif case == "head-race":
                assert result == {"status": "stale-head"} and exact_parents(repo, current) == (original,)
            else:
                expected = {
                    "same-slot": {"status": "semantic-conflict", "kinds": ["update-update"]},
                    "dangling-dependency": {"status": "semantic-conflict", "kinds": ["dependency"]},
                    "missing-source": {"status": "invalid-inventory"},
                    "wrong-base": {"status": "wrong-base-or-operation"},
                    "absent-commit": {"status": "wrong-base-or-operation"},
                    "outside-source": {"status": "unsupported-tree"},
                }
                assert result == expected[case] and current == original, (mode, case, result)
            results.append({"mode": mode, "case": case, **result})
    native_results = {mode: native_control(root / f"native-{mode}", mode) for mode in MODES}
    return {
        "git": GIT(root, "--version"), "coordinated_cases": len(results),
        "published_candidates": 3, "native_text_conflicts": native_results, "cases": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-git-core-coordinator-") as directory:
        result = check(Path(directory))
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
