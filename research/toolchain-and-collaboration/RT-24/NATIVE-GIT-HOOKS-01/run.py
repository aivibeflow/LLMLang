"""Compare native hook observations and actual branch outcomes on exact graph edits."""
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

from tests.test_candidate_graph_audit import declaration
from tests.test_rt24_merge_tree_gate import (
    CALLEE, CALLER, GraphImportError, MergeTreeGateExperiment, commit, git, import_closed,
    read_inventory, row,
)
from tests.test_rt24_semantic_merge_core import merge_inventories


HOOKS = ("pre-commit", "pre-merge-commit", "pre-applypatch",
         "post-applypatch", "post-merge", "post-commit", "post-rewrite")
HOOK = Path(__file__).with_name("hook.py").resolve()
OPERATION_HOOKS = {
    "commit": ("pre-commit", "post-commit"),
    "merge": ("pre-merge-commit", "post-merge"),
    "merge-no-verify": ("post-merge",),
    "manual-merge": ("pre-commit", "post-commit"),
    "cherry-pick": ("post-commit",),
    "rebase-merge": ("post-commit", "post-rewrite"),
    "rebase-apply": ("pre-applypatch", "post-applypatch", "post-rewrite"),
    "am": ("pre-applypatch", "post-applypatch"),
}


def run_git(repo, args, *, patch=None):
    return subprocess.run(
        ["git", "-c", "user.name=RT-24 fixture", "-c", "user.email=fixture@example.invalid", *args],
        cwd=repo, env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                       "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z",
                       "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z", "GIT_EDITOR": "true"},
        input=patch, capture_output=True, timeout=30,
    )


def revision(repo, ref):
    return git(repo, "rev-parse", ref).decode().strip()


def prepare(fixture, invalid):
    repo = fixture.repo
    git(repo, "switch", "--quiet", "-c", "ours", fixture.base)
    ours = commit(repo, {CALLEE: [row("callee", fixture.new)]})
    git(repo, "switch", "--quiet", "-c", "theirs", fixture.base)
    addition = fixture.caller if invalid else declaration("function", "function:independent")
    theirs = commit(repo, {CALLER: [row("caller", addition)]})
    inventories = [read_inventory(repo, rev) for rev in (fixture.base, ours, theirs)]
    combined = merge_inventories(*inventories)
    assert combined.status == ("graph-conflict" if invalid else "structural-candidate")
    return ours, theirs


def install_hooks(repo, directory, ledger):
    directory.mkdir()
    command = [sys.executable, str(HOOK)]
    for name in HOOKS:
        invocation = shlex.join([*command, name, str(ledger)])
        path = directory / name
        path.write_text(f'#!/bin/sh\nexec {invocation} "$@"\n', encoding="utf-8")
        path.chmod(0o700)
    git(repo, "config", "core.hooksPath", str(directory))


def perform(repo, operation, patch):
    if operation == "commit":
        git(repo, "checkout", "theirs", "--", CALLER)
        return run_git(repo, ("commit", "-m", "fixture candidate"))
    if operation == "manual-merge":
        staged = run_git(repo, ("merge", "--no-commit", "--no-ff", "theirs"))
        assert staged.returncode == 0, staged.stderr
        return run_git(repo, ("commit", "-m", "fixture merge"))
    commands = {
        "merge": ("merge", "--no-ff", "--no-edit", "theirs"),
        "merge-no-verify": ("merge", "--no-ff", "--no-edit", "--no-verify", "theirs"),
        "cherry-pick": ("cherry-pick", "theirs"),
        "rebase-merge": ("rebase", "--merge", "ours"),
        "rebase-apply": ("rebase", "--apply", "ours"),
        "am": ("am",),
    }
    return run_git(repo, commands[operation], patch=patch if operation == "am" else None)


def graph(repo, tree):
    try:
        import_closed(read_inventory(repo, tree))
    except GraphImportError:
        return "unclosed"
    return "closed"


def run_case(operation, invalid):
    fixture = MergeTreeGateExperiment()
    fixture.setUp()
    try:
        repo = fixture.repo
        ours, theirs = prepare(fixture, invalid)
        branch = "theirs" if operation.startswith("rebase") else "ours"
        initial = theirs if branch == "theirs" else ours
        git(repo, "switch", "--quiet", branch)
        patch = git(repo, "format-patch", "-1", "theirs", "--stdout")
        with TemporaryDirectory(prefix="rt24-hooks-observation-") as directory:
            directory = Path(directory)
            ledger = directory / "trace.ndjson"
            install_hooks(repo, directory / "hooks", ledger)
            result = perform(repo, operation, patch)
            observed = [json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
        selected = revision(repo, f"refs/heads/{branch}")
        head = revision(repo, "HEAD")
        expected_hooks = OPERATION_HOOKS[operation]
        blocked = invalid and expected_hooks[0].startswith("pre-")
        expected_hooks = expected_hooks[:1] if blocked else expected_hooks
        assert tuple(record["hook"] for record in observed) == expected_hooks
        assert result.returncode == int(blocked), (operation, result.stderr)
        selected_graph = graph(repo, selected)
        if blocked:
            assert selected == initial and selected_graph == "closed"
        else:
            assert selected != initial and selected_graph == ("unclosed" if invalid else "closed")
        head_detached = run_git(repo, ("symbolic-ref", "-q", "HEAD")).returncode != 0
        assert head_detached == (blocked and operation == "rebase-apply"), (operation, head)
        assert head == (ours if head_detached else selected)

        staged_tree = git(repo, "write-tree").decode().strip()
        for entry in observed:
            assert entry["index_tree"] == staged_tree, (operation, entry)
            assert entry["state"] == ("unclosed" if invalid else "closed"), (operation, entry)
            if entry["hook"].startswith("post-"):
                assert entry["head"] == selected
            if entry["hook"] == "post-rewrite":
                assert entry["args"] == ["rebase"]
        if not blocked:
            assert revision(repo, f"{selected}^{{tree}}") == staged_tree
        return {"operation": operation, "candidate_graph": "unclosed" if invalid else "closed",
                "git_status": result.returncode, "selected_before": initial, "selected_after": selected,
                "head_after": head, "head_detached": head_detached, "selected_graph": selected_graph,
                "candidate_installed": selected != initial, "hooks": observed}
    finally:
        fixture.doCleanups()


def evaluate():
    return {"format": "rt24-native-git-hooks/1",
            "git": subprocess.check_output(["git", "--version"], text=True).strip(),
            "python": sys.version.split()[0],
            "results": [run_case(operation, invalid) for operation in OPERATION_HOOKS for invalid in (False, True)]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    opts = parser.parse_args()
    opts.output.write_text(json.dumps(evaluate(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
