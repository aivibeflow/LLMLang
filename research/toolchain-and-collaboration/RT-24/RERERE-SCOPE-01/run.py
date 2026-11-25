#!/usr/bin/env python3
"""Measure when native rerere reuses a resolution outside a scoped approval."""

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
from src.semantic_graph import ContentStore, digest
from tests import test_rt24_merge_tree_gate as tree

POLICY = "decision-policy.json"
CASES = ("same_scope", "disjoint_declaration", "changed_choice", "changed_revision", "reversed_parents")
BACKENDS = ("files", "reftable")


def command(repo, *arguments, rerere=False, autoupdate=False, expect_success=True):
    env = {
        **os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
        "GIT_EDITOR": "true", "GIT_SEQUENCE_EDITOR": "true",
    }
    result = subprocess.run(
        ["git", "-c", "user.name=RT-24 fixture", "-c", "user.email=fixture@example.invalid",
         "-c", f"rerere.enabled={str(rerere).lower()}", "-c", f"rerere.autoupdate={str(autoupdate).lower()}",
         *arguments], cwd=repo, env=env, capture_output=True, text=True, timeout=30, check=expect_success,
    )
    return result


def git(repo, *arguments):
    return tree.git(repo, *arguments).decode().strip()


def target_declarations():
    store = ContentStore()
    contract = tree.declaration("contract", "contract:score", {"result": "Int"})
    contract_hash = publish_declaration(store, contract)
    providers = {role: tree.declaration("function", "function:score", {"offset": offset}, references=[{
        "reference_id": "provides", "relation": "provides_contract",
        "target_hash": contract_hash, "target_kind": "contract",
    }]) for role, offset in (("initial", 1), ("one", 2), ("two", 99))}
    target_hashes = {role: publish_declaration(store, row) for role, row in providers.items()}
    callers = {role: tree.row("caller", tree.declaration("function", "function:entry", call_sites=[{
        "call_site_id": "invoke", "targets": [{
            "target_id": "direct", "target_hash": target, "required_contract_hash": contract_hash,
            "condition": "entry-active",
        }],
    }])) for role, target in target_hashes.items()}
    provider_rows = [tree.row(f"provider.{role}", row) for role, row in providers.items()]
    return contract, provider_rows, callers, target_hashes


def commit_source_merge(repo, parents, chosen, record):
    git(repo, "switch", "--quiet", "--detach", parents[0])
    result = command(repo, "merge", "--no-ff", "--no-edit", parents[1], rerere=record, expect_success=False)
    assert result.returncode == 1 and git(repo, "ls-files", "--unmerged", "--", tree.CALLER)
    revision = tree.commit(repo, {tree.CALLER: [chosen]})
    if record:
        command(repo, "rerere", rerere=True)
    assert parents_of(repo, revision) == list(parents)
    return revision


def parents_of(repo, revision):
    return git(repo, "show", "-s", "--format=%P", revision).split()


def file_policy(repo, revision):
    parsed = json.loads(tree.git(repo, "show", f"{revision}:{POLICY}"))
    assert set(parsed) == {"choice", "revision"}
    assert parsed["choice"] in {"first", "second"} and type(parsed["revision"]) is int
    return parsed


def read(repo, revision):
    inventory = tree.read_inventory(repo, revision)
    store, snapshot = tree.import_closed(inventory)
    declaration = inventory.declarations["caller"]
    target = declaration["call_sites"][0]["targets"][0]["target_hash"]
    source = tree.source_evidence(inventory, store, snapshot, target)
    assert not source.reverse.discrepancies
    return {
        "tree": inventory.tree, "root": snapshot.root_hash, "caller": snapshot.mapping["caller"],
        "target": target, "required_contract": declaration["call_sites"][0]["targets"][0]["required_contract_hash"],
        "has_auxiliary": "auxiliary" in snapshot.mapping, "source_audit": source.reverse.evidence_id,
    }


def conflict_key(repo, base, parents, policy):
    previous = read(repo, base)
    parents_read = [read(repo, parent) for parent in parents]
    assert all(row["required_contract"] == previous["required_contract"] for row in parents_read)
    return {
        "path": tree.CALLER,
        "site": "caller/invoke/direct",
        "base_caller": previous["caller"],
        "ordered_parent_callers": [row["caller"] for row in parents_read],
        "required_contract": previous["required_contract"],
        "policy": digest(policy),
    }


def cache(repo):
    base = repo / ".git" / "rr-cache"
    return {entry.name: {item.name: sha256(item.read_bytes()).hexdigest() for item in sorted(entry.iterdir())}
            for entry in sorted(base.iterdir()) if entry.is_dir()}


def initial(repo, backend, case):
    git(repo, "init", "--quiet", "--template=", "--initial-branch=base", "--object-format=sha1",
        f"--ref-format={backend}")
    assert git(repo, "rev-parse", "--show-ref-format") == backend
    contract, provider_rows, callers, target_hashes = target_declarations()
    training_policy = {"choice": "first", "revision": 1}
    base = tree.commit(repo, {
        tree.MANIFEST: tree.manifest(tree.CONTRACT, tree.CALLEE, tree.CALLER),
        tree.CONTRACT: [tree.row("contract", contract)], tree.CALLEE: provider_rows,
        tree.CALLER: [callers["initial"]], POLICY: training_policy,
    })
    git(repo, "switch", "--quiet", "-c", "side-one", base)
    first = tree.commit(repo, {tree.CALLER: [callers["one"]], "one.txt": "first provider branch\n"})
    git(repo, "switch", "--quiet", "-c", "side-two", base)
    second = tree.commit(repo, {tree.CALLER: [callers["two"]], "two.txt": "second provider branch\n"})
    training_merge = commit_source_merge(repo, (first, second), callers["one"], True)
    initial_cache = cache(repo)
    assert len(initial_cache) == 1 and "postimage" in next(iter(initial_cache.values()))
    if case == "reversed_parents":
        reviewed_source = commit_source_merge(repo, (second, first), callers["two"], False)
    else:
        reviewed_source = training_merge
    assert cache(repo) == initial_cache, (case, cache(repo), initial_cache)

    destination_policy = dict(training_policy)
    if case == "changed_choice":
        destination_policy.update(choice="second", revision=2)
    elif case == "changed_revision":
        destination_policy["revision"] = 2
    git(repo, "switch", "--quiet", "-c", "destination", base)
    destination_files = {"destination.txt": "unrelated target edit\n", POLICY: destination_policy}
    if case == "disjoint_declaration":
        auxiliary = tree.declaration("function", "function:auxiliary", {"result": 42})
        destination_files[tree.CALLEE] = [*provider_rows, tree.row("auxiliary", auxiliary)]
    onto = tree.commit(repo, destination_files)
    return base, onto, training_merge, reviewed_source, initial_cache, target_hashes


def rebase(repo, base, onto, source_merge, autoupdate):
    git(repo, "switch", "--quiet", "--detach", source_merge)
    paused = command(repo, "rebase", "--rebase-merges", "--onto", onto, base,
                     rerere=True, autoupdate=autoupdate, expect_success=False)
    assert paused.returncode == 1
    assert "previous resolution" in paused.stderr
    staged = git(repo, "ls-files", "--unmerged", "--", tree.CALLER) == ""
    assert staged == autoupdate
    worktree = (repo / tree.CALLER).read_bytes()
    if not staged:
        git(repo, "add", tree.CALLER)
    index = tree.git(repo, "show", f":{tree.CALLER}")
    assert index == worktree
    command(repo, "rebase", "--continue", rerere=True, autoupdate=autoupdate)
    commit = git(repo, "rev-parse", "HEAD")
    parents = parents_of(repo, commit)
    assert len(parents) == 2 and all(parents_of(repo, parent) == [onto] for parent in parents)
    assert tree.git(repo, "show", f"{commit}:{tree.CALLER}") == index
    assert git(repo, "status", "--porcelain") == ""
    return commit, parents, staged, sha256(index).hexdigest()


def experiment(repo, backend, case, autoupdate):
    base, onto, training, source_merge, initial_cache, target_hashes = initial(repo, backend, case)
    trained_parents = parents_of(repo, training)
    trained_approval = conflict_key(repo, base, trained_parents, file_policy(repo, training))
    trained_caller = read(repo, training)["caller"]
    source = read(repo, source_merge)
    new_merge, new_parents, staged, proposal = rebase(repo, base, onto, source_merge, autoupdate)
    replay_cache = cache(repo)
    stable = {key: {name: checksum for name, checksum in files.items() if not name.startswith("thisimage")}
              for key, files in replay_cache.items()}
    assert stable == initial_cache

    destination_policy = file_policy(repo, new_merge)
    fresh_key = conflict_key(repo, onto, new_parents, destination_policy)
    fresh_parent = new_parents[0 if destination_policy["choice"] == "first" else 1]
    intended = read(repo, fresh_parent)
    current = read(repo, new_merge)
    assert current["caller"] == trained_caller and current["target"] == target_hashes["one"]
    assert current["has_auxiliary"] == (case == "disjoint_declaration")
    assert git(repo, "rev-parse", "destination") == onto
    assert tree.git(repo, "show", f"{new_merge}:one.txt") == b"first provider branch\n"
    assert tree.git(repo, "show", f"{new_merge}:two.txt") == b"second provider branch\n"
    assert source["target"] == target_hashes["two" if case == "reversed_parents" else "one"]
    expected_target = target_hashes["two" if case in {"changed_choice", "reversed_parents"} else "one"]
    assert intended["target"] == expected_target

    exact_projection = trained_approval == fresh_key and current["caller"] == intended["caller"]
    assert exact_projection == (case in {"same_scope", "disjoint_declaration"})
    same_git_commits = base == onto and trained_parents == new_parents
    assert not same_git_commits
    return {
        "backend": backend, "case": case, "autoupdate": autoupdate, "staged_by_rerere": staged,
        "original_base": base, "destination": onto, "training_merge": training, "reviewed_source": source_merge,
        "training_git_parents": trained_parents, "new_merge": new_merge, "new_parents": new_parents,
        "cache": initial_cache, "cache_after_replay": replay_cache, "proposal_blob_sha256": proposal, "source": source, "current": current,
        "cached_scope": trained_approval, "new_scope": fresh_key,
        "fresh_oracle_target": expected_target, "matches_fresh_target": current["target"] == expected_target,
        "source_closed": True, "exact_git_parent_gate": same_git_commits, "scoped_reuse_gate": exact_projection,
    }


def run(directory):
    version = subprocess.check_output(["git", "--version"], text=True).strip()
    assert version == "git version 2.52.0", version
    rows = []
    for backend, case, autoupdate in product(BACKENDS, CASES, (False, True)):
        repo = directory / f"{backend}-{case}-{autoupdate}"
        repo.mkdir()
        rows.append(experiment(repo, backend, case, autoupdate))
    for case in CASES:
        variants = [{key: value for key, value in row.items()
                     if key not in {"backend", "autoupdate", "staged_by_rerere"}}
                    for row in rows if row["case"] == case]
        assert all(row == variants[0] for row in variants)
    return {
        "schema": "llmlang-rt24-rerere-scope/1", "git": version, "python": platform.python_version(),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "native_cases": len(rows),
        "native_reused_proposals": len(rows),
        "closed_native_candidates": sum(row["source_closed"] for row in rows),
        "wrong_fresh_target": sum(not row["matches_fresh_target"] for row in rows),
        "staged_by_rerere": sum(row["staged_by_rerere"] for row in rows),
        "exact_git_parents_reuse": sum(row["exact_git_parent_gate"] for row in rows),
        "exact_scoped_reuse": sum(row["scoped_reuse_gate"] for row in rows),
        "observations": rows,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt24-rerere-scope-") as scratch:
        result = run(Path(scratch))
    observations = result.pop("observations")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "observations": [')
    print(",\n".join("    " + json.dumps(row) for row in observations))
    print("  ]\n}")
