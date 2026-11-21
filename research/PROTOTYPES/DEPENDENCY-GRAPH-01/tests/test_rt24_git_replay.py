"""Check source closure after real Git cherry-pick and rebase operations."""

from dataclasses import dataclass
import unittest

from tests import test_rt24_merge_tree_gate as tree
from src.semantic_graph import digest


@dataclass(frozen=True)
class ReplayObservation:
    operation: str
    patch_parent: str
    patch: str
    onto: str
    replayed_commit: str
    replayed_tree: str
    semantic_root: str

    @property
    def evidence_identity(self):
        return digest(("rt24-closed-replay/1", self.operation, self.patch_parent,
                       self.patch, self.onto, self.replayed_commit, self.replayed_tree,
                       self.semantic_root))


def admit_replay(repo, operation, patch_parent, patch, onto, replayed):
    """Require the captured single-parent patch and replay bases, then import."""
    def parent(commit):
        return tree.git(repo, "show", "-s", "--format=%P", commit).decode().strip()

    if operation not in ("cherry-pick", "rebase"):
        raise tree.InventoryError("unsupported operation")
    if parent(patch) != patch_parent or parent(replayed) != onto:
        raise tree.InventoryError("replay does not match the captured source and target parents")
    inventory = tree.read_inventory(repo, replayed)
    _, state = tree.import_closed(inventory)
    return ReplayObservation(operation, patch_parent, patch, onto, replayed,
                             inventory.tree, state.root_hash)


class GitReplayExperiment(unittest.TestCase):
    setUp = tree.MergeTreeGateExperiment.setUp

    def create_histories(self, retain):
        tree.git(self.repo, "switch", "--quiet", "-c", "topic", self.base)
        patch = tree.commit(self.repo, {tree.CALLER: [tree.row("caller", self.caller)]})
        tree.git(self.repo, "switch", "--quiet", "-c", "target", self.base)
        providers = [tree.row("callee", self.new)]
        if retain:
            providers.append(tree.row("old", self.old))
        onto = tree.commit(self.repo, {tree.CALLEE: providers})
        for commit in (self.base, patch, onto):
            tree.import_closed(tree.read_inventory(self.repo, commit))
        return patch, onto

    def replay(self, operation, patch, onto):
        if operation == "cherry-pick":
            tree.git(self.repo, "switch", "--quiet", "-c", "picked", onto)
            tree.git(self.repo, "cherry-pick", patch)
        else:
            tree.git(self.repo, "switch", "--quiet", "-c", "rebased", patch)
            tree.git(self.repo, "rebase", "--onto", onto, self.base)
        self.assertEqual(tree.git(self.repo, "status", "--porcelain"), b"")
        return tree.git(self.repo, "rev-parse", "HEAD").decode().strip()

    def test_clean_replays_can_drop_an_exact_provider_version(self):
        patch, onto = self.create_histories(retain=False)
        for operation in ("cherry-pick", "rebase"):
            with self.subTest(operation=operation):
                replayed = self.replay(operation, patch, onto)
                with self.assertRaisesRegex(tree.GraphImportError, self.old_hash):
                    admit_replay(self.repo, operation, self.base, patch, onto, replayed)

    def test_preserved_provider_closes_both_replays(self):
        patch, onto = self.create_histories(retain=True)
        observations = []
        for operation in ("cherry-pick", "rebase"):
            replayed = self.replay(operation, patch, onto)
            observed = admit_replay(self.repo, operation, self.base, patch, onto, replayed)
            observations.append(observed)
            inventory = tree.read_inventory(self.repo, replayed)
            store, snapshot = tree.import_closed(inventory)
            row = store.get(snapshot.mapping["caller"]).payload["call_sites"][0]["targets"][0]
            self.assertEqual(row["target_hash"], self.old_hash)
            self.assertEqual(snapshot.mapping["old"], self.old_hash)
            self.assertNotEqual(snapshot.mapping["callee"], self.old_hash)
        a, b = observations
        self.assertEqual((a.replayed_tree, a.semantic_root), (b.replayed_tree, b.semantic_root))
        self.assertNotEqual(a.evidence_identity, b.evidence_identity)

    def test_unrelated_parent_is_rejected_even_for_a_valid_tree(self):
        patch, onto = self.create_histories(retain=True)
        replayed = self.replay("cherry-pick", patch, onto)
        tree.import_closed(tree.read_inventory(self.repo, replayed))
        for before, proposed in ((onto, onto), (self.base, self.base)):
            with self.assertRaisesRegex(tree.InventoryError, "captured source and target parents"):
                admit_replay(self.repo, "cherry-pick", before, patch, proposed, replayed)

    def test_closure_and_parent_checks_do_not_prove_patch_correspondence(self):
        patch, onto = self.create_histories(retain=True)
        # This commit has the right parent and a closed tree, but adds no caller.
        inventory = tree.read_inventory(self.repo, onto)
        substitute = tree.git(self.repo, "commit-tree", inventory.tree, "-p", onto,
                              "-m", "same-parent substitute").decode().strip()
        outcome = admit_replay(self.repo, "cherry-pick", self.base, patch, onto, substitute)
        self.assertEqual(outcome.replayed_tree, inventory.tree)
        self.assertNotIn("caller", inventory.declarations)
