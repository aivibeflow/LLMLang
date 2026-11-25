#!/usr/bin/env python3
"""Compare recreated merges with checked source merge-only caller changes."""

from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_dependency_index import publish_declaration
from src.semantic_graph import ContentStore
from tests import test_rt24_merge_tree_gate as tree

CASES = {
    "ordinary_destination": ("migrate", "ordinary", False, "reapply"),
    "restored_terminal": ("migrate", "ordinary", True, "reapply"),
    "disjoint_semantic_destination": ("migrate", "disjoint", False, "reapply"),
    "exact_destination": ("migrate", "exact", False, "already_applied"),
    "competing_destination": ("migrate", "competing", False, "precondition_conflict"),
    "no_residual_disjoint": ("none", "disjoint", False, "no_residual"),
    "mixed_unrecognized_residual": ("mixed", "ordinary", False, "unsupported_residual"),
}
BACKENDS = ("files", "reftable")


def git(repo, *args, stdin=None):
    return tree.git(repo, *args, stdin=stdin).decode("utf-8").strip()


def controlled_git(repo, *args):
    env = {
        **os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
        "GIT_EDITOR": "true", "GIT_SEQUENCE_EDITOR": "true",
    }
    return subprocess.run(
        ["git", "-c", "user.name=RT-24 fixture", "-c", "user.email=fixture@example.invalid",
         "-c", "rerere.enabled=false", *args], cwd=repo, env=env, capture_output=True, check=True, timeout=30,
    ).stdout.decode("utf-8").strip()


def declarations():
    store = ContentStore()
    contract = tree.declaration("contract", "contract:score", {"result": "Int"})
    contract_hash = publish_declaration(store, contract)
    providers = {label: tree.declaration("function", "function:score", {"offset": offset}, references=[{
        "reference_id": "provides", "relation": "provides_contract",
        "target_hash": contract_hash, "target_kind": "contract",
    }]) for label, offset in (("old", 1), ("intended", 2), ("competing", 99))}
    target_hashes = {label: publish_declaration(store, value) for label, value in providers.items()}
    callers = {label: tree.declaration("function", "function:entry", call_sites=[{
        "call_site_id": "invoke", "targets": [{
            "target_id": "direct", "target_hash": target, "required_contract_hash": contract_hash,
            "condition": "entry-active",
        }],
    }]) for label, target in target_hashes.items()}
    return contract, providers, callers, target_hashes


def file_payload(rows):
    return (json.dumps(rows, indent=2) + "\n").encode()


def workspace_file(repo, path):
    return tree.git(repo, "show", f"HEAD:{path}")


def initial(repo, backend, residual, destination, tail, contract, providers, callers):
    git(repo, "init", "--quiet", "--template=", "--initial-branch=base", "--object-format=sha1",
        f"--ref-format={backend}")
    assert git(repo, "rev-parse", "--show-ref-format") == backend
    interface = [tree.row("contract", contract)]
    all_providers = [tree.row(f"callee.{label}", row) for label, row in providers.items()]
    base = tree.commit(repo, {
        tree.MANIFEST: tree.manifest(tree.CONTRACT, tree.CALLEE, tree.CALLER),
        tree.CONTRACT: interface, tree.CALLEE: all_providers,
        tree.CALLER: [tree.row("caller", callers["old"])],
        "destination.txt": "baseline\n",
    })
    git(repo, "switch", "--quiet", "-c", "destination", base)
    files = {"destination.txt": "keep destination bytes\n"}
    if destination == "disjoint":
        files[tree.CALLEE] = [*all_providers, tree.row("auxiliary", tree.declaration("function", "other", {"offset": 16}))]
    elif destination in {"exact", "competing"}:
        choice = "intended" if destination == "exact" else "competing"
        files[tree.CALLER] = [tree.row("caller", callers[choice])]
    onto = tree.commit(repo, files)

    git(repo, "switch", "--quiet", "-c", "left", base)
    left = tree.commit(repo, {"left.txt": "left side\n"})
    git(repo, "switch", "--quiet", "-c", "right", base)
    right = tree.commit(repo, {"right.txt": "right side\n"})
    git(repo, "switch", "--quiet", "-c", "topic", left)
    controlled_git(repo, "merge", "--no-commit", "--no-ff", right)
    if residual != "none":
        (repo / tree.CALLER).write_bytes(file_payload([tree.row("caller", callers["intended"])]))
    if residual == "mixed":
        (repo / "merge-only.txt").write_text("requires separately reviewed textual replay\n")
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "-m", "reviewed merge")
    source_merge = git(repo, "rev-parse", "HEAD")
    if tail:
        topic = tree.commit(repo, {tree.CALLER: [tree.row("caller", callers["old"])],
                                   "after.txt": "keep following commit\n"})
    else:
        topic = source_merge
    return base, onto, (left, right), source_merge, topic


def observe(repo, revision):
    inventory = tree.read_inventory(repo, revision)
    store, snapshot = tree.import_closed(inventory)
    _, caller = next(row for row in snapshot.selections if row[0] == "caller")
    target = inventory.declarations["caller"]["call_sites"][0]["targets"][0]["target_hash"]
    source = tree.source_evidence(inventory, store, snapshot, target)
    assert not source.reverse.discrepancies
    return {"tree": inventory.tree, "root": snapshot.root_hash, "caller": caller, "target": target,
            "source_audit": source.reverse.evidence_id,
            "has_auxiliary": "auxiliary" in snapshot.mapping}


def automatic_tree(repo, parents):
    assert len(parents) == 2
    return git(repo, "merge-tree", "--write-tree", *parents)


def parents_of(repo, commit):
    return git(repo, "show", "-s", "--format=%P", commit).split()


def changed_paths(repo, start, end):
    return git(repo, "diff", "--name-only", "-z", start, end).removesuffix("\0").split("\0") if start != end else []


def replay(repo, base, onto, topic):
    git(repo, "switch", "--quiet", "--detach", topic)
    controlled_git(repo, "rebase", "--rebase-merges", "--empty=keep", "--onto", onto, base)
    assert git(repo, "status", "--porcelain") == ""
    tip = git(repo, "rev-parse", "HEAD")
    merges = git(repo, "rev-list", "--merges", f"{onto}..{tip}").splitlines()
    assert len(merges) == 1
    for parent in parents_of(repo, merges[0]):
        assert parents_of(repo, parent) == [onto]
    return merges[0], tip


def review(source_auto, source_merge, source_paths, candidate_auto, candidate_merge):
    status = "unsupported_residual"
    if not source_paths:
        assert source_auto["root"] == source_merge["root"]
        status = "no_residual"
    elif source_paths == [tree.CALLER] and source_merge["caller"] != source_auto["caller"]:
        if candidate_auto["caller"] == source_merge["caller"]:
            status = "already_applied"
        elif candidate_auto["caller"] == source_auto["caller"]:
            status = "reapply"
        else:
            status = "precondition_conflict"
    assert candidate_auto["tree"] == candidate_merge["tree"]
    return status


def rebuild(repo, merge, original_merge, original_tip, approved_merge, tail):
    merge_parents = parents_of(repo, merge)
    git(repo, "switch", "--quiet", "--detach", merge)
    before = git(repo, "rev-parse", "HEAD")
    approved = tree.read_inventory(repo, original_merge).declarations["caller"]
    expected = [tree.row("caller", approved)]
    (repo / tree.CALLER).write_bytes(file_payload(expected))
    git(repo, "add", tree.CALLER)
    proposed = git(repo, "write-tree")
    new_commit = git(repo, "commit-tree", proposed, "-p", merge_parents[0], "-p", merge_parents[1],
                     stdin=b"checked merge-only call retarget\n")
    assert parents_of(repo, new_commit) == merge_parents
    assert observe(repo, new_commit)["caller"] == approved_merge["caller"]
    assert changed_paths(repo, merge, new_commit) == [tree.CALLER]
    assert git(repo, "rev-parse", "HEAD") == before
    git(repo, "switch", "--quiet", "--detach", new_commit)
    if tail:
        controlled_git(repo, "cherry-pick", original_tip)
    tip = git(repo, "rev-parse", "HEAD")
    return new_commit, tip


def experiment(repo, backend, name):
    residual, destination, tail, expected = CASES[name]
    contract, providers, callers, hashes = declarations()
    base, onto, parents, original_merge, original_tip = initial(
        repo, backend, residual, destination, tail, contract, providers, callers)
    assert parents_of(repo, original_merge) == list(parents)
    source_auto = observe(repo, automatic_tree(repo, parents))
    source_merge = observe(repo, original_merge)
    source_tip = observe(repo, original_tip)
    paths = changed_paths(repo, source_auto["tree"], source_merge["tree"])
    assert paths == {"none": [], "migrate": [tree.CALLER],
                     "mixed": ["merge-only.txt", tree.CALLER]}[residual]
    merge, tip = replay(repo, base, onto, original_tip)
    candidate_parents = parents_of(repo, merge)
    original_snapshots = [observe(repo, revision) for revision in parents]
    replayed_snapshots = [observe(repo, revision) for revision in candidate_parents]
    assert all(row["caller"] == source_auto["caller"] for row in original_snapshots)
    destination_snapshot = observe(repo, onto)
    assert all(row["root"] == destination_snapshot["root"] for row in replayed_snapshots)
    candidate_auto = observe(repo, automatic_tree(repo, candidate_parents))
    candidate_merge = observe(repo, merge)
    candidate_tip = observe(repo, tip)
    status = review(source_auto, source_merge, paths, candidate_auto, candidate_merge)
    assert status == expected

    terminal_root_gate = source_tip["root"] == candidate_tip["root"]
    correct_before_repair = status in {"no_residual", "already_applied"}
    assert correct_before_repair == (source_merge["caller"] == candidate_merge["caller"])
    repaired = None
    if status == "reapply":
        rebuilt_merge, rebuilt_tip = rebuild(repo, merge, original_merge, original_tip, source_merge, tail)
        repaired = {"merge_commit": rebuilt_merge, "tip_commit": rebuilt_tip, "merge": observe(repo, rebuilt_merge),
                    "tip": observe(repo, rebuilt_tip)}
        assert repaired["merge"]["target"] == hashes["intended"]
        assert repaired["tip"]["target"] == hashes["old" if tail else "intended"]
        assert repaired["tip"]["has_auxiliary"] == (destination == "disjoint")
        if tail:
            assert parents_of(repo, rebuilt_tip) == [rebuilt_merge]
            assert workspace_file(repo, "after.txt") == b"keep following commit\n"
    for path, content in (("destination.txt", b"keep destination bytes\n"),
                          ("left.txt", b"left side\n"), ("right.txt", b"right side\n")):
        assert workspace_file(repo, path) == content
    assert git(repo, "rev-parse", "topic") == original_tip
    assert git(repo, "rev-parse", "destination") == onto
    return {
        "backend": backend, "case": name, "base": base, "destination": onto,
        "source_parents": parents, "source_merge_commit": original_merge, "source_tip_commit": original_tip,
        "source_auto": source_auto, "source_merge": source_merge, "source_tip": source_tip,
        "source_merge_only_paths": paths, "candidate_merge_commit": merge, "candidate_tip_commit": tip,
        "candidate_parents": candidate_parents, "candidate_parent_snapshots": replayed_snapshots,
        "source_parent_snapshots": original_snapshots, "candidate_auto": candidate_auto,
        "candidate_merge": candidate_merge, "candidate_tip": candidate_tip,
        "closure_gate": True, "terminal_root_gate": terminal_root_gate,
        "checked_before_repair": correct_before_repair, "residual_gate": status,
        "repair": repaired, "original_refs_preserved": True,
    }


def run(directory):
    version = subprocess.check_output(["git", "--version"], text=True).strip()
    assert version == "git version 2.52.0", version
    cases = []
    for backend, name in product(BACKENDS, CASES):
        repo = directory / f"{backend}-{name}"
        repo.mkdir()
        cases.append(experiment(repo, backend, name))
    for name in CASES:
        same_case = [{key: value for key, value in row.items() if key != "backend"}
                     for row in cases if row["case"] == name]
        assert same_case[0] == same_case[1]
    assert all(row["terminal_root_gate"] and not row["checked_before_repair"]
               for row in cases if row["case"] == "restored_terminal")
    assert all(not row["terminal_root_gate"] and row["checked_before_repair"]
               for row in cases if row["case"] == "no_residual_disjoint")
    return {
        "schema": "llmlang-rt24-rebase-merge-residual/1", "git": version, "python": platform.python_version(),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "closed_native_candidates": sum(row["closure_gate"] for row in cases),
        "exact_old_terminal_root": sum(row["terminal_root_gate"] for row in cases),
        "correct_native_candidates": sum(row["checked_before_repair"] for row in cases),
        "verified_repairs": sum(row["repair"] is not None for row in cases),
        "refused_for_conflict_or_scope": sum(row["residual_gate"] in {"precondition_conflict", "unsupported_residual"}
                                             for row in cases),
        "observations": cases,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt24-merge-residual-") as scratch:
        result = run(Path(scratch))
    observations = result.pop("observations")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "observations": [')
    print(",\n".join("    " + json.dumps(row) for row in observations))
    print("  ]\n}")
