"""Compare Git driver scope in native merge, cherry-pick and rebase."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from tempfile import TemporaryDirectory

PROTOTYPE = Path(__file__).resolve().parents[3] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))

from src.semantic_graph import canonical_bytes
from tests.test_candidate_graph_audit import declaration
from tests.test_rt24_merge_tree_gate import (
    CALLEE, CALLER, GraphImportError, MergeTreeGateExperiment, commit, git, import_closed,
    read_inventory, row,
)
from tests.test_rt24_semantic_merge_core import merge_inventories


DRIVER = Path(__file__).with_name("driver.py").resolve()
OPERATIONS = {
    "merge": ("merge", "--no-commit", "--no-ff", "theirs"),
    "cherry-pick": ("cherry-pick", "theirs"),
    "rebase": ("rebase", "ours"),
}


def invoke(repo, args):
    return subprocess.run(
        ["git", "-c", "user.name=RT-24 fixture", "-c", "user.email=fixture@example.invalid", *args],
        cwd=repo, env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                      "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z",
                      "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z"},
        capture_output=True, timeout=30,
    )


def compact(values):
    return canonical_bytes(values).decode() + "\n"


def prepare(test, context):
    repo = test.repo
    base = commit(repo, {
        ".gitattributes": "program/callee.json merge=rt24 conflict-marker-size=11\n",
        CALLEE: compact([row("callee", test.old)]),
    })
    git(repo, "switch", "--quiet", "-c", "ours")
    ours = commit(repo, {CALLEE: compact([row("callee", test.new)])})
    git(repo, "switch", "--quiet", "-c", "theirs", base)
    other = declaration("function", "function:independent")
    right = [row("callee", test.old), row("independent", other)]
    if context == "same-slot":
        changed = {**test.old, "content": {"offset": 3}}
        right = [row("callee", changed)]
    patch = {CALLEE: compact(right)}
    if context == "external-caller":
        patch[CALLER] = [row("caller", test.caller)]
    theirs = commit(repo, patch)
    return base, ours, theirs


def run_case(operation, policy, context):
    fixture = MergeTreeGateExperiment()
    fixture.setUp()
    try:
        repo = fixture.repo
        commits = prepare(fixture, context)
        expected = merge_inventories(*(read_inventory(repo, revision) for revision in commits))
        base, ours, theirs = commits
        git(repo, "switch", "--quiet", "theirs" if operation == "rebase" else "ours")
        with TemporaryDirectory(prefix="rt24-driver-observation-") as directory:
            observation = Path(directory) / "invocations.jsonl"
            suffix = ' %O %A %B %L %P'
            if policy != "unconfigured":
                tool = [str(Path(directory) / "absent-rt24")] if policy == "missing" else [
                    sys.executable, str(DRIVER), policy, str(observation)]
                git(repo, "config", "merge.rt24.driver", shlex.join(tool) + suffix)
            result = invoke(repo, OPERATIONS[operation])
            calls = [json.loads(line) for line in observation.read_text().splitlines()] if observation.exists() else []
        expected_success = policy == "local-slots" and context != "same-slot"
        assert (result.returncode == 0) == expected_success, (operation, policy, context, result)
        unresolved = git(repo, "diff", "--name-only", "--diff-filter=U").decode().splitlines()
        assert unresolved == ([] if expected_success else [CALLEE]), (operation, unresolved)
        unresolved_stages = [
            int(record.split(b"\t", 1)[0].split()[-1])
            for record in git(repo, "ls-files", "-u", "-z").split(b"\0")[:-1]
        ]
        assert unresolved_stages == ([] if expected_success else [1, 2, 3]), unresolved_stages
        head_after = git(repo, "rev-parse", "HEAD").decode().strip()
        published = head_after != ours
        assert published == (expected_success and operation != "merge"), (operation, head_after)
        if policy in {"local-slots", "require-context"}:
            assert len(calls) == 1, calls
            call = calls[0]
            def blob(revision, path):
                return git(repo, "rev-parse", f"{revision}:{path}").decode().strip()
            assert call["blobs"] == [blob(revision, CALLEE) for revision in commits]
            assert call["path"] == CALLEE and call["marker_size"] == 11
            assert call["head"] == ours
            assert call["index_caller"] == blob(ours, CALLER)
        elif policy == "missing":
            assert b"absent-rt24" in result.stderr and not calls
        else:
            assert b"<<<<<<<<<<<" in (repo / CALLEE).read_bytes() and not calls

        tree = None
        selections = None
        graph_status = None
        if expected_success:
            tree = git(repo, "write-tree").decode().strip()
            try:
                _, snapshot = import_closed(read_inventory(repo, tree))
            except GraphImportError:
                graph_status = "unclosed"
                assert expected.status == "graph-conflict"
            else:
                graph_status = "closed"
                selections = dict(snapshot.selections)
                assert tuple(sorted(selections.items())) == expected.selections

        return {"operation": operation, "policy": policy, "context": context,
                "git_status": result.returncode, "calls": calls, "transaction_tree": tree,
                "unmerged": unresolved, "unmerged_stages": unresolved_stages,
                "head_after": head_after, "new_commit_before_semantic_gate": published,
                "coordinator_status": expected.status,
                "assembled_graph": graph_status, "selections": selections,
                "commits": dict(zip(("base", "ours", "theirs"), commits, strict=True))}
    finally:
        fixture.doCleanups()


def evaluate():
    cases = [
        (operation, "local-slots", context)
        for operation in OPERATIONS for context in ("independent", "external-caller")
    ] + [
        ("merge", "local-slots", "same-slot"),
        ("merge", "unconfigured", "independent"),
        ("merge", "missing", "independent"),
    ] + [(operation, "require-context", "independent") for operation in OPERATIONS]
    outcomes = [run_case(*case) for case in cases]
    for position in range(0, 6, 2):
        accepted, unsafe = outcomes[position:position + 2]
        assert accepted["calls"] == unsafe["calls"], (accepted, unsafe)
        assert accepted["assembled_graph"] == "closed" and unsafe["assembled_graph"] == "unclosed"
    return {"format": "rt24-native-merge-driver/1",
            "git": subprocess.check_output(["git", "--version"], text=True).strip(),
            "python": sys.version.split()[0], "results": outcomes}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(evaluate(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
