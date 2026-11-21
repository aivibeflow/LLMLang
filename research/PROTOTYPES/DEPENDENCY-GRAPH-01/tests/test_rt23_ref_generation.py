"""Exercise a coordinated Git generation in the publication transaction."""

from dataclasses import dataclass
import subprocess
import unittest

from tests import test_rt23_commit_recovery as recovery
from tests.test_rt24_merge_tree_gate import git


GENERATION = "refs/llmlang/generation/main"


def generation_value(repo, previous, commit):
    body = f"rt23-branch-generation/1\n{previous}\n{commit}\n".encode("ascii")
    return git(repo, "hash-object", "-w", "--stdin", stdin=body).decode().strip()


def advance(repo, old_branch, new_branch, old_generation, receipt=None):
    next_token = generation_value(repo, old_generation, new_branch)
    rows = ["start", f"update {recovery.BRANCH} {new_branch} {old_branch}",
            f"update {GENERATION} {next_token} {old_generation}"]
    if receipt is not None:
        rows.append(f"create {receipt} {new_branch}")
    rows.extend(("prepare", "commit", ""))
    git(repo, "update-ref", "--stdin", stdin="\n".join(rows).encode("ascii"))
    return next_token


@dataclass(frozen=True)
class Captured:
    prepared: recovery.Prepared
    generation: str


def publish(repo, captured, before_transaction=lambda: None):
    prepared = captured.prepared
    outcome = recovery.inspect(repo, prepared)
    if outcome != "retryable":
        return outcome
    if recovery.ref(repo, GENERATION) != captured.generation:
        return "stale-generation"
    if not recovery.matches_candidate(repo, prepared):
        return "invalid-candidate"

    before_transaction()
    try:
        advance(repo, prepared.parents[0], prepared.candidate, captured.generation,
                prepared.receipt)
    except subprocess.CalledProcessError:
        outcome = recovery.inspect(repo, prepared)
        if outcome != "retryable":
            return outcome
        if recovery.ref(repo, GENERATION) != captured.generation:
            return "stale-generation"
        raise
    return recovery.inspect(repo, prepared)


class RefGenerationExperiment(unittest.TestCase):
    def setUp(self):
        # Reuse the frozen exact-tree candidate with dirty independent worktree files.
        recovery.CommitRecoveryExperiment.setUp(self)
        initial = generation_value(self.repo, "initial", self.base)
        git(self.repo, "update-ref", GENERATION, initial)
        self.captured = Captured(self.plan, initial)

    @staticmethod
    def contract(name):
        return recovery.CommitRecoveryExperiment.contract(name)

    def bounce(self):
        live_head = recovery.ref(self.repo, recovery.BRANCH)
        generation = recovery.ref(self.repo, GENERATION)
        intermediate = recovery.commit_object(
            self.repo, self.plan.tree, (live_head,), "intermediate coordinated update",
        )
        updated = advance(self.repo, live_head, intermediate, generation)
        restored = advance(self.repo, intermediate, live_head, updated)
        self.assertEqual(recovery.ref(self.repo, recovery.BRANCH), live_head)
        self.assertNotEqual(generation, restored)

    def test_move_away_and_back_invalidates_unpublished_approval(self):
        self.bounce()
        self.assertEqual(recovery.ref(self.repo, recovery.BRANCH), self.base)
        self.assertEqual(recovery.inspect(self.repo, self.plan), "retryable")
        self.assertEqual(publish(self.repo, self.captured), "stale-generation")
        self.assertIsNone(recovery.ref(self.repo, self.plan.receipt))

    def test_transaction_checks_the_generation_after_preflight(self):
        self.assertEqual(publish(self.repo, self.captured, self.bounce), "stale-generation")
        self.assertEqual(recovery.ref(self.repo, recovery.BRANCH), self.base)
        self.assertIsNone(recovery.ref(self.repo, self.plan.receipt))

    def test_published_receipt_recovers_after_coordinated_movements(self):
        self.assertEqual(publish(self.repo, self.captured), "published")
        self.assertNotEqual(recovery.ref(self.repo, GENERATION), self.captured.generation)
        self.bounce()
        self.assertEqual(publish(self.repo, self.captured), "published")
        self.assertEqual(recovery.ref(self.repo, self.plan.receipt), self.plan.candidate)

    def test_uncoordinated_ref_writes_do_not_change_the_generation(self):
        git(self.repo, "update-ref", recovery.BRANCH, self.other_parent, self.base)
        git(self.repo, "update-ref", recovery.BRANCH, self.base, self.other_parent)
        self.assertEqual(recovery.ref(self.repo, GENERATION), self.captured.generation)
        self.assertEqual(publish(self.repo, self.captured), "published")