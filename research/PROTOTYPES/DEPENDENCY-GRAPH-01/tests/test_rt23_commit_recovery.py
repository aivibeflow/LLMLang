"""Native Git experiment for publication of a previously validated candidate."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from src.semantic_graph import digest
from tests.test_candidate_graph_audit import declaration
from tests.test_rt24_merge_tree_gate import (
    CONTRACT, MANIFEST, commit, git, import_closed, manifest, read_inventory, row,
)


BRANCH = "refs/heads/main"


def ref(repo: Path, name: str) -> str | None:
    try:
        return git(repo, "rev-parse", "--verify", "--quiet", name).decode().strip()
    except subprocess.CalledProcessError as error:
        if error.returncode != 1:
            raise
        return None


def commit_object(repo: Path, tree: str, parents: tuple[str, ...], message: str) -> str:
    args = ["commit-tree", tree]
    for parent in parents:
        args.extend(("-p", parent))
    return git(repo, *args, "-m", message).decode().strip()


@dataclass(frozen=True)
class Prepared:
    operation: str
    tree: str
    semantic_root: str
    parents: tuple[str, ...]
    candidate: str

    @property
    def receipt(self) -> str:
        return f"refs/llmlang/receipts/{digest(self.operation)}"


def inspect(repo: Path, plan: Prepared) -> str:
    receipt = ref(repo, plan.receipt)
    head = ref(repo, BRANCH)
    if receipt is None:
        return "retryable" if head == plan.parents[0] else "stale"
    if receipt != plan.candidate:
        return "receipt-conflict"
    if not matches_candidate(repo, plan):
        return "receipt-conflict"
    return "published" if head == receipt else "published-branch-moved"


def matches_candidate(repo: Path, plan: Prepared) -> bool:
    metadata = git(repo, "show", "-s", "--format=%T%n%P", plan.candidate).decode().splitlines()
    if metadata != [plan.tree, " ".join(plan.parents)]:
        return False
    _, snapshot = import_closed(read_inventory(repo, plan.candidate))
    return snapshot.root_hash == plan.semantic_root


def update_refs(repo: Path, plan: Prepared) -> None:
    commands = (
        f"start\nupdate {BRANCH} {plan.candidate} {plan.parents[0]}\n"
        f"create {plan.receipt} {plan.candidate}\nprepare\ncommit\n"
    )
    git(repo, "update-ref", "--stdin", stdin=commands.encode("ascii"))


def publish(repo: Path, plan: Prepared) -> str:
    outcome = inspect(repo, plan)
    if outcome == "retryable":
        if not matches_candidate(repo, plan):
            return "invalid-candidate"
        try:
            update_refs(repo, plan)
        except subprocess.CalledProcessError:
            outcome = inspect(repo, plan)
            if outcome == "retryable":
                raise
            return outcome
        outcome = inspect(repo, plan)
    return outcome


class CommitRecoveryExperiment(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix="rt23-commit-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "--quiet", "--template=", "--initial-branch=main", "--object-format=sha1")
        self.base = commit(self.repo, {
            MANIFEST: manifest(CONTRACT), CONTRACT: [self.contract("old")],
            "selected.txt": "old selected\n", "unrelated.txt": "old unrelated\n",
        })
        base_tree = ref(self.repo, f"{self.base}^{{tree}}")
        self.other_parent = commit_object(self.repo, base_tree, (self.base,), "second parent")
        (self.repo / CONTRACT).write_text(json.dumps([self.contract("new")]), encoding="utf-8")
        (self.repo / "selected.txt").write_text("new selected\n", encoding="utf-8")
        unrelated = self.repo / "unrelated.txt"
        unrelated.write_text("user staged\n", encoding="utf-8")
        git(self.repo, "add", "--", "unrelated.txt")
        unrelated.write_text("user unstaged\n", encoding="utf-8")

        index = self.root / "candidate.index"
        git(self.repo, "read-tree", self.base, index=index)
        git(self.repo, "add", "--", CONTRACT, "selected.txt", index=index)
        tree = git(self.repo, "write-tree", index=index).decode().strip()
        _, before = import_closed(read_inventory(self.repo, self.base))
        _, after = import_closed(read_inventory(self.repo, tree))
        self.assertNotEqual(before.root_hash, after.root_hash)
        parents = (self.base, self.other_parent)
        candidate = commit_object(self.repo, tree, parents, "fixture operation 1")
        self.plan = Prepared("fixture operation 1", tree, after.root_hash, parents, candidate)
        self.journal = self.root / "prepared.json"
        self.journal.write_text(json.dumps(asdict(self.plan)), encoding="utf-8")

    @staticmethod
    def contract(version: str) -> dict:
        return row("contract", declaration("contract", "contract:demo", {"version": version}))

    def reload(self) -> Prepared:
        data = json.loads(self.journal.read_text(encoding="utf-8"))
        return Prepared(**{**data, "parents": tuple(data["parents"])})

    def test_retry_before_ref_update_publishes_only_the_validated_paths(self):
        plan = self.reload()
        self.assertEqual(inspect(self.repo, plan), "retryable")
        index_before = (self.repo / ".git/index").read_bytes()
        # A selected path changes after validation. Rebuilding from the live
        # worktree here would publish a different tree.
        (self.repo / "selected.txt").write_text("later edit\n", encoding="utf-8")
        self.assertEqual(publish(self.repo, plan), "published")
        self.assertEqual(git(self.repo, "show", "main:selected.txt"), b"new selected\n")
        self.assertEqual(git(self.repo, "show", "main:unrelated.txt"), b"old unrelated\n")
        self.assertEqual(git(self.repo, "show", ":unrelated.txt"), b"user staged\n")
        self.assertEqual((self.repo / "unrelated.txt").read_text(), "user unstaged\n")
        self.assertEqual((self.repo / "selected.txt").read_text(), "later edit\n")
        self.assertEqual((self.repo / ".git/index").read_bytes(), index_before)

    def test_lost_reply_after_update_recovers_without_a_second_commit(self):
        update_refs(self.repo, self.plan)
        plan = self.reload()
        for _ in range(2):
            self.assertEqual(publish(self.repo, plan), "published")
            self.assertEqual(ref(self.repo, BRANCH), plan.candidate)
        self.assertEqual(git(self.repo, "rev-list", "--first-parent", "--count", BRANCH), b"2\n")

    def test_ref_movement_between_check_and_update_leaves_no_receipt(self):
        plan = self.reload()
        self.assertEqual(inspect(self.repo, plan), "retryable")
        git(self.repo, "update-ref", BRANCH, self.other_parent, self.base)
        with self.assertRaises(subprocess.CalledProcessError):
            update_refs(self.repo, plan)
        self.assertEqual(inspect(self.repo, plan), "stale")
        self.assertIsNone(ref(self.repo, plan.receipt))

    def test_existing_receipt_rejects_the_entire_ref_transaction(self):
        git(self.repo, "update-ref", self.plan.receipt, self.other_parent)
        with self.assertRaises(subprocess.CalledProcessError):
            update_refs(self.repo, self.plan)
        self.assertEqual(ref(self.repo, BRANCH), self.base)
        self.assertEqual(inspect(self.repo, self.plan), "receipt-conflict")

    def test_commit_with_same_tree_and_parents_does_not_identify_the_operation(self):
        lookalike = commit_object(self.repo, self.plan.tree, self.plan.parents, "another operation")
        git(self.repo, "update-ref", BRANCH, lookalike, self.base)
        self.assertEqual(inspect(self.repo, self.plan), "stale")

    def test_receipt_verifies_ordered_parents_and_semantic_root(self):
        mismatches = (replace(self.plan, parents=(self.base,)),
                      replace(self.plan, semantic_root="different snapshot"),
                      replace(self.plan, tree=ref(self.repo, f"{self.base}^{{tree}}")))
        for altered in mismatches:
            self.assertEqual(publish(self.repo, altered), "invalid-candidate")
        self.assertEqual(ref(self.repo, BRANCH), self.base)
        self.assertIsNone(ref(self.repo, self.plan.receipt))
        update_refs(self.repo, self.plan)
        for altered in (*mismatches, replace(self.plan, parents=self.plan.parents[::-1])):
            self.assertEqual(inspect(self.repo, altered), "receipt-conflict")

    def test_later_branch_movement_preserves_the_historical_receipt(self):
        update_refs(self.repo, self.plan)
        next_commit = commit_object(self.repo, self.plan.tree, (self.plan.candidate,), "later work")
        git(self.repo, "update-ref", BRANCH, next_commit, self.plan.candidate)
        self.assertEqual(publish(self.repo, self.reload()), "published-branch-moved")
        self.assertEqual(ref(self.repo, BRANCH), next_commit)

    def test_oid_compare_and_swap_cannot_see_a_move_away_and_back(self):
        git(self.repo, "update-ref", BRANCH, self.other_parent, self.base)
        git(self.repo, "update-ref", BRANCH, self.base, self.other_parent)
        self.assertEqual(publish(self.repo, self.plan), "published")


if __name__ == "__main__":
    unittest.main()
