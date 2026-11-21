"""Compare expected semantic patch composition with an observed Git replay tree."""

from dataclasses import dataclass
import unittest

from src.semantic_graph import digest
from tests import test_rt24_merge_tree_gate as tree
from tests.test_rt23_commit_recovery import commit_object, ref
from tests.test_rt24_semantic_merge_core import merge_inventories


class ReplayMismatch(ValueError):
    pass


@dataclass(frozen=True)
class Reconciled:
    commits: tuple[str, str, str]
    pins: tuple[tuple[str, str, str | None], ...]
    output_tree: str
    output_root: str

    @property
    def identity(self):
        return digest(("rt24-replay-patch/1", self.commits, self.pins, self.output_tree, self.output_root))


def reconcile(repo, parent, patch, onto, replay):
    def parents(commit):
        return tree.git(repo, "show", "-s", "--format=%P", commit).decode().split()

    if parents(patch) != [parent] or parents(replay) != [onto]:
        raise ReplayMismatch("unexpected source or destination parent")
    base, target, source, result = (tree.read_inventory(repo, commit)
                                    for commit in (parent, onto, patch, replay))
    expected = merge_inventories(base, target, source)
    if expected.status != "structural-candidate":
        raise ReplayMismatch(f"semantic composition yielded {expected.status}")
    _, imported = tree.import_closed(result)
    if imported.selections != expected.selections:
        raise ReplayMismatch("observed selections differ from semantic patch composition")
    return Reconciled((parent, patch, onto), expected.inputs, result.tree, imported.root_hash)


class ReplayPatchExperiment(unittest.TestCase):
    setUp = tree.MergeTreeGateExperiment.setUp

    def histories(self):
        tree.git(self.repo, "switch", "--quiet", "-c", "topic", self.base)
        patch = tree.commit(self.repo, {tree.CALLER: [tree.row("caller", self.caller)]})
        tree.git(self.repo, "switch", "--quiet", "-c", "target", self.base)
        onto = tree.commit(self.repo, {
            tree.CALLEE: [tree.row("callee", self.new), tree.row("retained", self.old)],
        })
        return patch, onto

    def cherry_pick(self, patch):
        tree.git(self.repo, "cherry-pick", patch)
        return ref(self.repo, "HEAD")

    def test_native_replay_agrees_with_independent_semantic_composition(self):
        patch, onto = self.histories()
        picked = self.cherry_pick(patch)
        tree.git(self.repo, "switch", "--quiet", "-c", "replayed", patch)
        tree.git(self.repo, "rebase", "--onto", onto, self.base)
        rebased = ref(self.repo, "HEAD")
        a = reconcile(self.repo, self.base, patch, onto, picked)
        b = reconcile(self.repo, self.base, patch, onto, rebased)
        self.assertEqual(a, b)
        self.assertEqual(a.pins[1][0], tree.read_inventory(self.repo, onto).tree)

    def test_closed_same_parent_substitute_fails_semantic_check(self):
        patch, onto = self.histories()
        closed = tree.read_inventory(self.repo, onto)
        substitute = commit_object(self.repo, closed.tree, (onto,), "caller omitted")
        tree.import_closed(tree.read_inventory(self.repo, substitute))
        with self.assertRaisesRegex(ReplayMismatch, "selections differ"):
            reconcile(self.repo, self.base, patch, onto, substitute)

    def test_same_semantic_patch_with_unreviewed_regular_file_has_distinct_evidence(self):
        patch, onto = self.histories()
        picked = self.cherry_pick(patch)
        original = reconcile(self.repo, self.base, patch, onto, picked)
        other = tree.commit(self.repo, {"notes.txt": "unreviewed\n"})
        inventory = tree.read_inventory(self.repo, other)
        substitute = commit_object(self.repo, inventory.tree, (onto,), "changed notes")
        observed = reconcile(self.repo, self.base, patch, onto, substitute)
        self.assertEqual(observed.output_root, original.output_root)
        self.assertNotEqual(observed.output_tree, original.output_tree)
        self.assertNotEqual(observed.identity, original.identity)

    def test_source_and_destination_callee_conflict_blocks_reconciliation(self):
        alternate = {**self.old, "content": {"offset": 3}}
        tree.git(self.repo, "switch", "--quiet", "-c", "left", self.base)
        patch = tree.commit(self.repo, {tree.CALLEE: [tree.row("callee", self.new)]})
        tree.git(self.repo, "switch", "--quiet", "-c", "right", self.base)
        onto = tree.commit(self.repo, {tree.CALLEE: [tree.row("callee", alternate)]})
        substitute = commit_object(self.repo, tree.read_inventory(self.repo, onto).tree,
                                   (onto,), "arbitrary resolution")
        with self.assertRaisesRegex(ReplayMismatch, "slot-conflict"):
            reconcile(self.repo, self.base, patch, onto, substitute)