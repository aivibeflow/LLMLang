"""Compare one authoritative Git journal ref with branch-plus-receipt publication."""
import argparse
from dataclasses import asdict, replace
from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
spec = spec_from_file_location("ref_visibility", HERE.parent / "REF-VISIBILITY-01" / "run.py")
visibility = module_from_spec(spec)
spec.loader.exec_module(visibility)
from src.semantic_graph import canonical_bytes
from tests import test_rt23_commit_recovery as recovery
from tests.test_rt24_merge_tree_gate import git as git_bytes

git = visibility.git
JOURNAL = "refs/llmlang/journal/main"


def write_entry(repo, plan, previous):
    record = {"format": "rt23-single-journal/1", "ref": recovery.BRANCH, "plan": asdict(plan)}
    blob = git_bytes(repo, "hash-object", "-w", "--stdin", stdin=canonical_bytes(record)).decode().strip()
    tree = git_bytes(repo, "mktree", stdin=f"100644 blob {blob}\tpublication.json\n".encode()).decode().strip()
    return recovery.commit_object(repo, tree, (previous, plan.candidate), "exact publication entry")


def initialize(repo, backend):
    plan = visibility.setup(repo, backend)
    base = plan.parents[0]
    empty = git_bytes(repo, "mktree", stdin=b"").decode().strip()
    genesis = recovery.commit_object(repo, empty, (base,), "journal genesis")
    git(repo, "update-ref", JOURNAL, genesis)
    decision = write_entry(repo, plan, genesis)
    return plan, genesis, decision


def read_plan(repo, entry):
    raw = git_bytes(repo, "show", f"{entry}:publication.json")
    data = json.loads(raw)
    assert canonical_bytes(data) == raw
    assert data["format"] == "rt23-single-journal/1" and data["ref"] == recovery.BRANCH
    plan = data["plan"]
    return recovery.Prepared(**{**plan, "parents": tuple(plan["parents"])})


def read_outcome(repo, head, plan):
    """Resolve exact publication from the pinned journal, retaining explicit conflicts."""
    current = head
    while True:
        parents = git(repo, "show", "-s", "--format=%P", current).split()
        if len(parents) == 1:
            assert not git(repo, "ls-tree", current)
            return "undecided"
        assert len(parents) == 2
        predecessor, candidate = parents
        stored = read_plan(repo, current)
        if stored.operation == plan.operation:
            if candidate != plan.candidate or stored != plan:
                return "journal-conflict"
            return "published" if recovery.matches_candidate(repo, plan) else "journal-conflict"
        current = predecessor


def observe(repo, plan):
    head = recovery.ref(repo, JOURNAL)
    branch = recovery.ref(repo, recovery.BRANCH)
    assert head is not None
    return {"branch": branch, "receipt": recovery.ref(repo, plan.receipt),
            "journal": head, "paired_result": recovery.inspect(repo, plan),
            "journal_result": read_outcome(repo, head, plan)}


def apply_projection(repo, plan, head):
    """Project the current exact journal decision onto the unchanged expected branch."""
    assert read_plan(repo, head) == plan
    assert read_outcome(repo, head, plan) == "published"
    branch = recovery.ref(repo, recovery.BRANCH)
    if branch == plan.candidate:
        return "already-current"
    if branch != plan.parents[0]:
        return "branch-conflict"
    command = (f"start\nverify {JOURNAL} {head}\n"
               f"update {recovery.BRANCH} {plan.candidate} {branch}\nprepare\ncommit\n")
    git_bytes(repo, "update-ref", "--stdin", stdin=command.encode())
    return "projected"


def expected_cas_failure(repo, *args):
    try:
        git(repo, *args)
    except subprocess.CalledProcessError as error:
        assert b"expected" in error.stderr
    else:
        raise AssertionError("stale compare-and-swap unexpectedly succeeded")


def kill_at_rename(repo, preload, suffix, target, old, new, *, before=None):
    environment = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                   "LD_PRELOAD": str(preload), "LLMLANG_PAUSE_RENAME_SUFFIX": suffix}
    with subprocess.Popen(["git", "update-ref", target, new, old], cwd=repo, env=environment,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        try:
            visibility.await_stop(process)
            paused_state = before() if before else None
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)
    assert process.returncode == -signal.SIGKILL
    return paused_state


def suffix_for(backend, ref):
    return f"/.git/{ref}" if backend == "files" else "/.git/reftable/tables.list"


def paired(repo, plan, genesis, preload, backend):
    suffix = suffix_for(backend, recovery.BRANCH)
    observed, returncode = visibility.cut(repo, plan, preload, suffix, True)
    state = observe(repo, plan)
    assert state["branch"] == observed["branch"] == plan.candidate
    assert state["journal"] == genesis and state["journal_result"] == "undecided"
    if backend == "files":
        assert state["receipt"] is None and state["paired_result"] == "stale"
    else:
        assert state["receipt"] == plan.candidate and state["paired_result"] == "published"
    assert recovery.matches_candidate(repo, plan)
    return {"at_cut": observed, "after_kill": state, "returncode": returncode}


def journal_first(repo, plan, genesis, decision, preload, backend):
    initial = observe(repo, plan)
    assert initial["journal_result"] == "undecided"
    stopped = kill_at_rename(repo, preload, suffix_for(backend, JOURNAL), JOURNAL, genesis, decision,
                             before=lambda: observe(repo, plan))
    after = observe(repo, plan)
    assert stopped == after and after["journal_result"] == "published"
    assert after["branch"] == plan.parents[0] and after["receipt"] is None
    return {"before": initial, "at_cut": stopped, "after_kill": after}


def collision_and_history(repo, plan, genesis, decision, directory):
    base = plan.parents[0]
    # An exact prepared commit can also be reached by an ordinary branch writer.
    git(repo, "update-ref", recovery.BRANCH, plan.candidate, base)
    undecided = observe(repo, plan)
    assert undecided["journal_result"] == "undecided"
    git(repo, "update-ref", recovery.BRANCH, base, plan.candidate)

    unrelated = recovery.commit_object(repo, plan.tree, (base,), "a different exact prepared commit")
    other = replace(plan, operation="competing operation", candidate=unrelated)
    competing_decision = write_entry(repo, other, genesis)
    git(repo, "update-ref", JOURNAL, decision, genesis)
    expected_cas_failure(repo, "update-ref", JOURNAL, competing_decision, genesis)
    assert read_outcome(repo, decision, other) == "undecided"
    assert read_outcome(repo, decision, replace(plan, candidate=unrelated)) == "journal-conflict"
    assert apply_projection(repo, plan, decision) == "projected"
    assert apply_projection(repo, plan, decision) == "already-current"

    successor = recovery.commit_object(repo, plan.tree, (plan.candidate,), "successor candidate")
    later_plan = replace(plan, operation="later operation", parents=(plan.candidate,), candidate=successor)
    later = write_entry(repo, later_plan, decision)
    git(repo, "update-ref", JOURNAL, later, decision)
    assert apply_projection(repo, later_plan, later) == "projected"
    assert read_outcome(repo, later, plan) == "published"
    assert read_outcome(repo, decision, later_plan) == "undecided"

    clone = directory / "clone"
    git(directory, "clone", "--quiet", "--no-local", str(repo), str(clone))
    absent_in_default_clone = recovery.ref(clone, JOURNAL) is None
    assert absent_in_default_clone
    git(clone, "fetch", "--quiet", "origin", f"{JOURNAL}:{JOURNAL}")
    git(clone, "fsck", "--full")
    assert recovery.ref(clone, JOURNAL) == later
    assert read_outcome(clone, later, plan) == read_outcome(clone, later, later_plan) == "published"
    return {"branch_only": undecided, "journal_conflict_rejected": True, "stale_journal_cas_rejected": True,
            "original_result_after_later_entry": read_outcome(clone, later, plan), "fetched_journal": later,
            "default_clone_omits_journal": absent_in_default_clone}


def verify(directory):
    version = git(directory, "--version")
    compiler = subprocess.check_output(["gcc", "-dumpfullversion"], text=True).strip()
    assert version == "git version 2.52.0" and compiler == "14.2.0" and sys.platform == "linux"
    preload = directory / "pause_rename.so"
    instrument = HERE.parent / "REF-VISIBILITY-01" / "pause_rename.c"
    subprocess.run(["gcc", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC", str(instrument),
                    "-o", str(preload), "-ldl"], check=True, timeout=10)
    rows = {}
    for backend in ("files", "reftable"):
        for case in ("paired-kill", "journal-kill-retry", "journal-kill-divergence", "unmanaged-and-history"):
            repo = directory / f"{backend}-{case}"
            repo.mkdir()
            plan, genesis, decision = initialize(repo, backend)
            if case == "paired-kill":
                result = paired(repo, plan, genesis, preload, backend)
            elif case.startswith("journal-kill"):
                result = journal_first(repo, plan, genesis, decision, preload, backend)
                if case == "journal-kill-retry":
                    outcomes = [apply_projection(repo, plan, decision) for _ in range(2)]
                    assert outcomes == ["projected", "already-current"]
                    assert recovery.ref(repo, recovery.BRANCH) == plan.candidate
                    assert git(repo, "rev-list", "--first-parent", "--count", recovery.BRANCH) == "2"
                    result["projection_retries"] = outcomes
                else:
                    foreign = recovery.commit_object(repo, plan.tree, plan.parents, "unmanaged branch move")
                    git(repo, "update-ref", recovery.BRANCH, foreign, plan.parents[0])
                    outcome = apply_projection(repo, plan, decision)
                    assert outcome == "branch-conflict"
                    assert recovery.ref(repo, recovery.BRANCH) == foreign
                    result["projection_retry"] = outcome
                result["after_retry"] = observe(repo, plan)
                assert result["after_retry"]["journal_result"] == "published"
            else:
                result = collision_and_history(repo, plan, genesis, decision, repo)
            rows[f"{backend}/{case}"] = {"plan": asdict(plan), "decision": decision, **result}
    repo = directory / "reftable-unpublished-table"
    repo.mkdir()
    plan, genesis, decision = initialize(repo, "reftable")
    stopped = kill_at_rename(repo, preload, ".ref", JOURNAL, genesis, decision,
                             before=lambda: observe(repo, plan))
    after = observe(repo, plan)
    assert stopped == after and after["journal"] == genesis and after["journal_result"] == "undecided"
    assert after["branch"] == plan.parents[0]
    assert (repo / ".git/reftable/tables.list.lock").exists()
    rows["reftable/unpublished-table"] = {
        "plan": asdict(plan), "decision": decision, "at_cut": stopped, "after_kill": after,
        "abandoned_table_lock": True,
    }
    return {"format": "rt23-single-journal/1", "git": version, "gcc": compiler,
            "python": sys.version.split()[0], "cases": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-single-git-journal-") as scratch:
        data = verify(Path(scratch))
    args.output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
