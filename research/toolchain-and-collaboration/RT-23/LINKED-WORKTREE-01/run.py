"""Check a Git publication receipt independently of a linked worktree's index and files."""

import argparse
import fcntl
from hashlib import sha256
import json
from pathlib import Path
import shlex
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from tests import test_rt23_commit_recovery as recovery
from tests import test_rt24_merge_tree_gate as source


SELECTED = (source.CONTRACT, "selected.txt")


def git(repo, *args, **options):
    return source.git(repo, *args, **options).decode("utf-8").strip()


def setup(parent):
    repo = parent / "coordinator"
    repo.mkdir()
    git(repo, "init", "--quiet", "--template=", "--initial-branch=main", "--object-format=sha1")

    def declaration(version):
        return source.row("contract", source.declaration("contract", "contract:item", {"version": version}))

    baseline = source.commit(repo, {
        source.MANIFEST: source.manifest(source.CONTRACT), source.CONTRACT: [declaration("old")],
        "selected.txt": "base selection\n", "unselected.txt": "base unselected\n",
    })
    git(repo, "branch", "-m", "coordinator")
    git(repo, "branch", "main", baseline)
    target = parent / "target"
    git(repo, "worktree", "add", "--quiet", target, "main")
    semantic_path = target / source.CONTRACT
    semantic_path.write_text(json.dumps([declaration("approved")]) + "\n", encoding="utf-8")
    (target / "selected.txt").write_text("approved selection\n", encoding="utf-8")

    private_index = parent / "candidate.index"
    git(target, "read-tree", baseline, index=private_index)
    git(target, "add", "--", *SELECTED, index=private_index)
    candidate_tree = git(target, "write-tree", index=private_index)
    _, snapshot = source.import_closed(source.read_inventory(repo, candidate_tree))
    candidate = recovery.commit_object(repo, candidate_tree, (baseline,), "linked candidate")
    prepared = recovery.Prepared("linked worktree", candidate_tree, snapshot.root_hash, (baseline,), candidate)
    return repo, target, prepared


def fingerprint(target, paths):
    """Capture index entries and selected working bytes in one bounded observation."""
    return {
        path: {"entry": git(target, "ls-files", "--stage", "--", path),
               "working_sha256": sha256((target / path).read_bytes()).hexdigest()}
        for path in paths
    }


def read_state(repo, target, prepared):
    paths = (*SELECTED, "unselected.txt")
    return {
        "branch": recovery.ref(repo, recovery.BRANCH),
        "target_head": recovery.ref(target, "HEAD"),
        "coordinator_head": recovery.ref(repo, "HEAD"),
        "receipt": recovery.ref(repo, prepared.receipt),
        "status": git(target, "status", "--porcelain=v1", "--untracked-files=all").splitlines(),
        "index_tree": git(target, "write-tree"),
        "index": {path: git(target, "show", f":{path}") for path in paths},
        "working": {path: (target / path).read_text(encoding="utf-8").rstrip("\n") for path in paths},
        "published_selection": git(repo, "show", "main:selected.txt"),
    }


def prepare_hook(repo, target, lock, observation, *, cooperative):
    """Run or defer a native index/file edit at Git's ref prepare boundary."""
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(exist_ok=True)
    hook = hooks / "reference-transaction"
    destination = shlex.quote(str(target))
    edit = (f"printf '%s\\n' 'late edit at ref prepare' > {destination}/selected.txt"
            f" && git -C {destination} add -- selected.txt")
    if cooperative:
        command = f"flock -n {shlex.quote(str(lock))} sh -c {shlex.quote(edit)}"
    else:
        command = f"({edit})"
    hook.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = prepared ]; then\n'
        f"  if {command}; then\n"
        f"    echo edited > {shlex.quote(str(observation))}\n"
        "  else\n"
        f"    echo deferred > {shlex.quote(str(observation))}\n"
        "  fi\n"
        "fi\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)


def run_case(parent, case):
    repo, target, prepared = setup(parent)
    if case in {"materialized_and_staged", "coordinated_writer", "bypass_lock", "unselected_edits"}:
        git(target, "add", "--", *SELECTED)
    baseline = fingerprint(target, SELECTED)
    if case == "selected_working_edit":
        (target / "selected.txt").write_text("user unstaged after preparation\n", encoding="utf-8")
    elif case == "selected_index_edit":
        git(target, "add", "--", "selected.txt")
    elif case == "unselected_edits":
        path = target / "unselected.txt"
        path.write_text("user staged\n", encoding="utf-8")
        git(target, "add", "--", "unselected.txt")
        path.write_text("user unstaged\n", encoding="utf-8")
        (target / "new.txt").write_text("user untracked\n", encoding="utf-8")

    before = read_state(repo, target, prepared)
    lock = parent / "workspace.lock"
    observation = parent / "concurrent-result"
    if case in {"mutation_on_ref_prepare", "coordinated_writer", "bypass_lock"}:
        prepare_hook(repo, target, lock, observation, cooperative=case == "coordinated_writer")

    gate = "preflight_then_ref"
    with lock.open("wb") as coordinator_lock:
        if case in {"coordinated_writer", "bypass_lock"}:
            fcntl.flock(coordinator_lock, fcntl.LOCK_EX)
            gate = "coordinated_preflight_then_ref"
        if case == "ref_only":
            gate = "ref_only"
        admitted = fingerprint(target, SELECTED) == baseline
        if gate == "ref_only" or admitted:
            result = recovery.publish(repo, prepared)
        else:
            result = "stale_selection"
    after = read_state(repo, target, prepared)
    if after["target_head"] != after["branch"] or after["coordinator_head"] != before["coordinator_head"]:
        raise AssertionError("Checked-out linked branch should advance independently of coordinator HEAD")
    if result == "published":
        if not all(after[key] == prepared.candidate for key in ("branch", "target_head", "receipt")):
            raise AssertionError("Branch and receipt must refer to the exact approved commit")
        if not recovery.matches_candidate(repo, prepared):
            raise AssertionError("Receipt does not identify the closed published tree")
        if after["published_selection"] != "approved selection":
            raise AssertionError("The transaction included different regular-file content")
    else:
        if after != before or after["receipt"] is not None:
            raise AssertionError("Preflight rejection changed local or published state")
    return {
        "policy": gate, "preflight_pin_matches": admitted, "status": result, "before": before, "after": after,
        "concurrent_edit": observation.read_text().strip() if observation.exists() else None,
        "approved_tree": prepared.tree, "semantic_root": prepared.semantic_root,
        "workspace_index_matches_approved_tree": after["index_tree"] == prepared.tree,
        "workspace_selected_file_matches_approved": after["working"]["selected.txt"] == "approved selection",
        "workspace_selected_index_matches_approved": all(
            after["index"][path] == git(repo, "show", f"{prepared.candidate}:{path}") for path in SELECTED
        ),
    }


def verify():
    cases = {
        "ref_only": ("published", True, False, True),
        "materialized_and_staged": ("published", True, True, True),
        "selected_working_edit": ("stale_selection", False, False, False),
        "selected_index_edit": ("stale_selection", False, False, True),
        "unselected_edits": ("published", True, False, True),
        "mutation_on_ref_prepare": ("published", True, False, False),
        "coordinated_writer": ("published", True, True, True),
        "bypass_lock": ("published", True, False, False),
    }
    observations = {}
    with TemporaryDirectory(prefix="llmlang-linked-worktree-") as root:
        version = git(Path(root), "--version")
        if version != "git version 2.52.0":
            raise ValueError(version)
        for case, expected in cases.items():
            parent = Path(root) / case
            parent.mkdir()
            row = run_case(parent, case)
            status = (row["status"], row["preflight_pin_matches"],
                      row["workspace_index_matches_approved_tree"], row["workspace_selected_file_matches_approved"])
            if status != expected:
                raise AssertionError((case, expected, status))
            observations[case] = row

    for case in ("ref_only", "unselected_edits"):
        row = observations[case]
        if row["before"]["index"] != row["after"]["index"] or row["before"]["working"] != row["after"]["working"]:
            raise AssertionError("Ref publication should leave the target index and local files intact")
    unselected_case = observations["unselected_edits"]
    if not unselected_case["workspace_selected_index_matches_approved"]:
        raise AssertionError("Unrelated staging should preserve the approved selected entries")
    unselected = unselected_case["after"]
    if (unselected["index"]["unselected.txt"], unselected["working"]["unselected.txt"]) != (
        "user staged", "user unstaged",
    ) or "?? new.txt" not in unselected["status"]:
        raise AssertionError("Unselected staged, unstaged and untracked content must be preserved")
    for case in ("mutation_on_ref_prepare", "bypass_lock"):
        race = observations[case]
        if (race["concurrent_edit"] != "edited"
                or race["after"]["index"]["selected.txt"] != "late edit at ref prepare"):
            raise AssertionError("The target index did not accept an uncoordinated Git edit")
    if observations["coordinated_writer"]["concurrent_edit"] != "deferred":
        raise AssertionError("Cooperating edits should defer while the publication lock is held")
    return {"format": "rt23-linked-worktree-publication/1", "python": sys.version.split()[0],
            "git": version, "flock": subprocess.check_output(["flock", "--version"], text=True).strip(),
            "cases": observations}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(verify(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
