"""Compare endpoint equality with retained selection history in native Git."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_graph import digest
from tests import test_rt24_merge_tree_gate as source


SLOT = "reviewed"


def git(repo, *args):
    return source.git(repo, *args).decode("utf-8").strip()


def snapshot(repo, commit):
    inventory = source.read_inventory(repo, commit)
    _, state = source.import_closed(inventory)
    return {"commit": commit, "tree": inventory.tree, "root": state.root_hash,
            "selection": state.mapping.get(SLOT)}


def observe_history(repo, baseline, candidate):
    """Require actual linear parent links and readable, closed source at each step."""
    cursor = candidate
    reverse_path = [candidate]
    while cursor != baseline:
        try:
            commit = git(repo, "cat-file", "commit", cursor)
        except subprocess.CalledProcessError:
            return "missing_commit", []
        headers = commit.split("\n\n", 1)[0].splitlines()
        parents = [line.removeprefix("parent ") for line in headers if line.startswith("parent ")]
        if not parents:
            return "baseline_outside_history", []
        if len(parents) != 1:
            return "nonlinear_history", []
        cursor = parents[0]
        reverse_path.append(cursor)

    try:
        return "complete", [snapshot(repo, commit) for commit in reversed(reverse_path)]
    except subprocess.CalledProcessError:
        return "missing_commit_or_tree", []
    except (source.InventoryError, source.GraphImportError):
        return "invalid_source", []


def policies(repo, baseline, candidate):
    end = snapshot(repo, candidate)
    endpoint_match = baseline["selection"] == end["selection"]
    root_match = baseline["root"] == end["root"]
    tree_match = baseline["tree"] == end["tree"]
    status, path = observe_history(repo, baseline["commit"], candidate)
    if status != "complete":
        lifecycle = "unknown"
    elif any(step["selection"] is None for step in path):
        lifecycle = "interrupted"
    else:
        lifecycle = "continuous"
    receipt = digest(("rt24-retained-slot-history/1", SLOT, path)) if status == "complete" else None
    return {"terminal": end, "path": path, "history": status, "lifecycle": lifecycle,
            "equal_value": endpoint_match, "equal_root": root_match, "equal_tree": tree_match,
            "value_bound_proof_reusable": endpoint_match,
            "slot_bound_approval_reusable": endpoint_match and lifecycle == "continuous",
            "history_receipt": receipt}


def histories(repo):
    source.git(repo, "init", "--quiet", "--template=", "--initial-branch=base", "--object-format=sha1")
    reviewed = source.row(SLOT, source.declaration("function", "function:reviewed", {"offset": 1}))
    edited = source.row(SLOT, source.declaration("function", "function:reviewed", {"offset": 2}))
    other = source.row("other", source.declaration("function", "function:other", {"offset": 9}))
    initial = [reviewed, other]
    baseline = source.commit(repo, {source.MANIFEST: source.manifest(source.CALLEE),
                                    source.CALLEE: initial, "notes.txt": "base\n"})

    def branch(name, start=baseline):
        source.git(repo, "switch", "--quiet", "-c", name, start)

    def change(rows):
        return source.commit(repo, {source.CALLEE: rows})

    branch("continuous")
    source.commit(repo, {"notes.txt": "changed\n"})
    continuous = source.commit(repo, {"notes.txt": "base\n"})

    branch("recreated")
    deletion = change([other])
    recreated = change(initial)

    branch("other-recreated")
    change([reviewed])
    other_recreated = change(initial)

    branch("edited-restored")
    revision = change([edited, other])
    edited_restored = change(initial)

    branch("terminated")
    source.commit(repo, {"notes.txt": "terminal deletion\n"})
    terminated = change([other])

    branch("rewritten")
    source.git(repo, "merge", "--quiet", "--squash", recreated)
    source.git(repo, "commit", "--quiet", "--allow-empty", "-m", "squashed zero diff")
    rewritten = git(repo, "rev-parse", "HEAD")

    branch("ordinary-edit")
    ordinary_edit = source.commit(repo, {"notes.txt": "ordinary edit\n"})

    # Retain the recreated branch as a second parent while restoring its content.
    branch("merged", continuous)
    source.git(repo, "merge", "--quiet", "--no-ff", "-m", "both histories", recreated)
    merged = git(repo, "rev-parse", "HEAD")

    branch("invalid-prefix")
    source.commit(repo, {source.MANIFEST: None})
    invalid_prefix = source.commit(repo, {source.MANIFEST: source.manifest(source.CALLEE)})

    tree_oid = git(repo, "rev-parse", f"{baseline}^{{tree}}")
    unrelated = git(repo, "commit-tree", tree_oid, "-m", "unrelated equal tree")
    return baseline, {
        "continuous": continuous, "recreated": recreated, "other_recreated": other_recreated,
        "edited_restored": edited_restored, "changed_endpoint": revision, "terminated": terminated,
        "rewritten_to_zero_diff": rewritten, "ordinary_edit": ordinary_edit, "nonlinear": merged,
        "unrelated_equal_tree": unrelated, "invalid_prefix": invalid_prefix,
        "omitted_deletion": deletion,
    }


def verify():
    version = subprocess.check_output(["git", "--version"], text=True).strip()
    if version != "git version 2.52.0":
        raise ValueError(version)
    with TemporaryDirectory(prefix="llmlang-history-") as directory:
        root = Path(directory)
        repo = root / "source"
        repo.mkdir()
        start, candidates = histories(repo)
        baseline = snapshot(repo, start)
        deletion = candidates.pop("omitted_deletion")
        results = {case: policies(repo, baseline, tip) for case, tip in candidates.items()}
        source.git(root, "clone", "--quiet", "--depth=1", "--branch", "recreated",
                   repo.as_uri(), "shallow")
        results["shallow"] = policies(root / "shallow", baseline, candidates["recreated"])

        if git(repo, "show", "-s", "--format=%P", candidates["recreated"]) != deletion:
            raise AssertionError("The retained recreated history did not record its deletion")
        if git(repo, "show", "-s", "--format=%P", candidates["rewritten_to_zero_diff"]) != start:
            raise AssertionError("The zero-diff control must only retain its baseline parent")
        expected = {
            "continuous": ("complete", "continuous", True, True, True, True),
            "recreated": ("complete", "interrupted", True, True, True, False),
            "other_recreated": ("complete", "continuous", True, True, True, True),
            "edited_restored": ("complete", "continuous", True, True, True, True),
            "changed_endpoint": ("complete", "continuous", False, False, False, False),
            "terminated": ("complete", "interrupted", False, False, False, False),
            "rewritten_to_zero_diff": ("complete", "continuous", True, True, True, True),
            "ordinary_edit": ("complete", "continuous", True, True, False, True),
            "nonlinear": ("nonlinear_history", "unknown", True, True, True, False),
            "unrelated_equal_tree": ("baseline_outside_history", "unknown", True, True, True, False),
            "invalid_prefix": ("invalid_source", "unknown", True, True, True, False),
            "shallow": ("missing_commit", "unknown", True, True, True, False),
        }
        fields = ("history", "lifecycle", "equal_value", "equal_root", "equal_tree",
                  "slot_bound_approval_reusable")
        for case, row in results.items():
            actual = tuple(row[field] for field in fields)
            if actual != expected[case]:
                raise AssertionError((case, expected[case], actual))
        receipts = [row["history_receipt"] for row in results.values() if row["history_receipt"]]
        if len(set(receipts)) != len(receipts):
            raise AssertionError("Distinct retained histories produced duplicate receipts")
        return {"schema": "rt24-retained-slot-history/1", "git": version, "python": sys.version.split()[0],
                "selected_slot": SLOT, "baseline": baseline, "cases": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(verify(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
