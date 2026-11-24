"""Exercise native Git mergetool, an exit-code control and the RT-24 coordinator."""
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

from src.semantic_dependency_index import publish_declaration
from src.semantic_graph import ContentStore, canonical_bytes
from tests.test_candidate_graph_audit import declaration
from tests.test_rt24_merge_tree_gate import (
    CALLEE, CALLER, CONTRACT, MANIFEST, GraphImportError, commit, git, import_closed, manifest,
    read_inventory, row,
)

THIS = Path(__file__).resolve().parent
NOTES = "notes.txt"


def invoke(repo, *args, **extra_environment):
    return subprocess.run(
        ["git", "-c", "user.name=RT-24 fixture", "-c", "user.email=fixture@example.invalid", *args],
        cwd=repo, env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                       **extra_environment}, capture_output=True, timeout=30,
    )


def pending(repo):
    return git(repo, "diff", "--name-only", "--diff-filter=U", "-z").decode().split("\0")[:-1]


def configure(repo, mode):
    adapter = shlex.join([sys.executable, str(THIS / "mergetool.py")])
    arguments = '"$BASE" "$LOCAL" "$REMOTE" "$MERGED"'
    commands = {
        "coordinator": f"{adapter} {arguments}",
        "status-only": 'git checkout --ours -- "$MERGED"',
        "wrong-base": f'{adapter} "$LOCAL" "$LOCAL" "$REMOTE" "$MERGED"',
        "missing": shlex.join([str(repo / "absent-tool")]) + f" {arguments}",
    }
    git(repo, "config", "mergetool.rt24.cmd", commands[mode])
    git(repo, "config", "mergetool.rt24.trustExitCode", "true")
    git(repo, "config", "mergetool.keepBackup", "false")


def line(rows):
    return canonical_bytes(rows).decode() + "\n"


def prepare(repo, case):
    git(repo, "init", "--quiet", "--template=", "--initial-branch=base", "--object-format=sha1")
    store = ContentStore()
    contract = declaration("contract", "contract:score", {"result": "Int"})
    contract_hash = publish_declaration(store, contract)
    old = declaration("function", "function:score", {"offset": 1}, references=[{
        "reference_id": "provides", "relation": "provides_contract",
        "target_hash": contract_hash, "target_kind": "contract",
    }])
    old_hash = publish_declaration(store, old)
    new = {**old, "content": {"offset": 2}}
    other = declaration("function", "function:independent")
    caller = declaration("function", "function:entry", call_sites=[{
        "call_site_id": "invoke", "targets": [{
            "target_id": "direct", "target_hash": old_hash,
            "required_contract_hash": contract_hash, "condition": "entry-active",
        }],
    }])
    base = commit(repo, {
        MANIFEST: manifest(CONTRACT, CALLEE, CALLER), CONTRACT: [row("contract", contract)],
        CALLEE: line([row("callee", old)]), CALLER: [], NOTES: "base\n",
    })
    ours = {CALLEE: line([row("callee", new)]), NOTES: "ours\n"}
    theirs = {CALLEE: line([row("callee", old), row("independent", other)])}
    if case == "ordinary-conflict":
        theirs[NOTES] = "theirs\n"
    if case == "same-slot":
        theirs[CALLEE] = line([row("callee", {**old, "content": {"offset": 3}})])
    if case in {"cross-file-conflict", "clean-text-invalid-graph", "ordinary-fallback"}:
        theirs[CALLER] = [row("caller", caller)]
    if case == "clean-text-invalid-graph":
        del theirs[CALLEE]
    for name, content in (("ours", ours), ("theirs", theirs)):
        git(repo, "switch", "--quiet", "-c", name, base)
        revision = commit(repo, content)
        import_closed(read_inventory(repo, revision))
    git(repo, "switch", "--quiet", "ours")
    operations = {
        "cherry-pick": ("cherry-pick", "theirs"),
        "rebase": ("rebase", "theirs"),
    }
    operation = operations.get(case, ("merge", "--no-commit", "--no-ff", "theirs"))
    result = invoke(repo, *operation)
    expected = 0 if case == "clean-text-invalid-graph" else 1
    assert result.returncode == expected, (case, result.stdout, result.stderr)
    return result.returncode


def observe(repo, case, mode, diagnostic, wanted_pending, graph):
    operation_status = prepare(repo, case)
    before = pending(repo)
    prior = {name: (repo / name).read_bytes() for name in before}
    if mode == "stale-index":
        mode = "coordinator"
        staged = declaration("function", "function:unexpected")
        (repo / CALLER).write_text(line([row("unexpected", staged)]), encoding="utf-8")
        git(repo, "add", "--", CALLER)
    index_before = git(repo, "ls-files", "--stage", "-z")
    command = None
    if mode is not None:
        configure(repo, mode)
        command = invoke(repo, "mergetool", "--no-prompt", "--tool=rt24", "--", CALLEE)
        assert command.returncode == (1 if diagnostic else 0), (case, command.stdout, command.stderr)
        if diagnostic:
            assert diagnostic.encode() in command.stderr, (case, command.stderr)
            assert (repo / CALLEE).read_bytes() == prior[CALLEE], case
            assert git(repo, "ls-files", "--stage", "-z") == index_before, case
    elif case == "ordinary-fallback":
        # Built-in Git leaves its textual conflict for explicit user resolution.
        assert b"<<<<<<<" in prior[CALLEE]
    after = pending(repo)
    assert after == wanted_pending, (case, before, after)
    assert (repo / NOTES).read_bytes() == (prior[NOTES] if NOTES in after else b"ours\n")

    tree = None
    if not after:
        tree = git(repo, "write-tree").decode().strip()
        inventory = read_inventory(repo, tree)
        try:
            _, snapshot = import_closed(inventory)
        except GraphImportError:
            assert graph is False, case
            slots = None
        else:
            assert graph is True, case
            slots = sorted(snapshot.mapping)
            assert slots == (["callee", "contract"] if mode == "status-only" else
                             ["callee", "contract", "independent"]), (case, slots)
    else:
        slots = None
    commits = {ref: git(repo, "rev-parse", ref).decode().strip() for ref in ("base", "ours", "theirs")}
    return {"case": case, "adapter": mode, "git_operation_status": operation_status,
            "commits": commits, "resolved_index_tree": tree,
            "before": before, "after": after,
            "mergetool_status": None if command is None else command.returncode,
            "diagnostic": diagnostic, "complete_index_graph_closes": graph, "selected_slots": slots}


def run():
    cases = (
        ("composable", "coordinator", "", [], True),
        ("ordinary-conflict", "coordinator", "", [NOTES], None),
        ("same-slot", "coordinator", "slot-conflict update-update/callee", [CALLEE], None),
        ("cross-file-conflict", "coordinator", "graph-conflict", [CALLEE], None),
        ("clean-text-invalid-graph", None, "", [], False),
        ("cherry-pick", "coordinator", "single-merge-required", [CALLEE], None),
        ("rebase", "coordinator", "single-merge-required", [CALLEE], None),
        ("composable", "wrong-base", "input-stage-mismatch", [CALLEE], None),
        ("composable", "stale-index", "staged-semantic-candidate-differs", [CALLEE], None),
        ("composable", "status-only", "", [], True),
        ("composable", "missing", "absent-tool", [CALLEE], None),
        ("ordinary-fallback", None, "", [CALLEE], None),
    )
    results = []
    for case in cases:
        with TemporaryDirectory(prefix="rt24-mergetool-") as directory:
            results.append(observe(Path(directory), *case))
    status_only = next(item for item in results if item["adapter"] == "status-only")
    assert "independent" not in status_only["selected_slots"]
    return {"format": "rt24-native-mergetool/1",
            "git": subprocess.check_output(["git", "--version"], text=True).strip(),
            "python": sys.version.split()[0], "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    options = parser.parse_args()
    options.output.write_text(json.dumps(run(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
