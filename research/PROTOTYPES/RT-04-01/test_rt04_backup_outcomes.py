"""Check live role obligations independently of the foreign diagnostic."""

from collections import Counter
from itertools import permutations, product
from typing import get_args
from unittest import TestCase

from rt04_backup_outcomes import Policy, consider, receipt
from rt04_backup_roles import BackupPair
from rt04_backup_source_roles import parse, routes
from rt04_owned_call_match import MatchArm, Obligation, check_result_arms


_OUTCOMES = (
    ("ok", None, True, "owned"),
    ("clean_error", None, False, None),
    ("indeterminate", None, False, "reconcile"),
    ("indeterminate", None, True, "reconcile"),
    ("ok", "ok", False, None),
    ("ok", "consumed_error", False, None),
    ("ok", "retained_error", True, "retained"),
    ("ok", "indeterminate", False, "reconcile"),
    ("ok", "indeterminate", True, "reconcile"),
)


def compatible(left, right, first_live):
    source, destination = left
    next_source, next_destination = right
    conflict = first_live and (destination in right or source == next_destination)
    return next_source != next_destination and not conflict


class ForeignOutcomeTests(TestCase):
    def test_error_after_finish_can_consume_or_retain_both_roles(self):
        active = BackupPair("a", "b")
        proposal = BackupPair("b", "a")
        consumed = consider("bounded_roles", active, proposal, receipt("ok", "consumed_error"))
        retained = consider("bounded_roles", active, proposal, receipt("ok", "retained_error"))
        self.assertTrue(consumed.admits)
        self.assertIsNone(consumed.roles)
        self.assertFalse(retained.admits)
        self.assertEqual(retained.roles, active)
        self.assertEqual(retained.output.obligations, {Obligation("handle", "retained")})

    def test_uncertain_result_carries_roles_without_a_retryable_handle(self):
        observed = receipt("indeterminate")
        active = BackupPair("a", "b")
        self.assertEqual(observed.obligations, {Obligation("handle", "reconcile")})
        compatible_share = BackupPair("a", "c")
        self.assertTrue(consider("bounded_roles", active, compatible_share, observed).admits)
        self.assertFalse(consider("quarantine", active, compatible_share, observed).admits)
        for policy in ("bounded_roles", "quarantine"):
            with self.subTest(policy=policy):
                self.assertTrue(consider(policy, active, BackupPair("c", "d"), observed).admits)
                refusal = consider(policy, active, BackupPair("b", "a"), observed)
                self.assertFalse(refusal.admits)
                self.assertEqual(refusal.roles, active)
                self.assertEqual(refusal.output, observed)
        with self.assertRaisesRegex(ValueError, "requires a usable backup"):
            receipt("indeterminate", "ok")

    def test_a_finish_statement_does_not_establish_consumption_on_error(self):
        program = parse("backup(a, b)\nif p:\n    finish_first()\nbackup(c, b)")
        for route in frozenset(routes(program)):
            for disposition in ("consumed_error", "retained_error", "indeterminate"):
                observed = receipt("ok", None if route.retains_first else disposition)
                decision = consider("bounded_roles", route.first, route.second, observed)
                self.assertEqual(decision.admits, not route.retains_first and disposition == "consumed_error")

    def test_match_must_forward_retained_and_reconciliation_payloads(self):
        cases = frozenset(receipt(init, finish) for init, finish, _, _ in _OUTCOMES)
        arms = tuple(MatchArm(case, ("handle",) if case.obligations else ()) for case in cases)
        self.assertFalse(check_result_arms(cases, arms, output="tagged_outcome"))
        issues = check_result_arms(cases, arms, output="plain_result")
        self.assertEqual({(issue.code, issue.case.tag) for issue in issues}, {
            ("ERROR_CANNOT_CARRY_OBLIGATIONS", "InitUncertain"),
            ("ERROR_CANNOT_CARRY_OBLIGATIONS", "FinishErrorRetained"),
            ("ERROR_CANNOT_CARRY_OBLIGATIONS", "FinishUncertain"),
        })

    def test_all_dispositions_and_pairs(self):
        expected = {
            "release_on_error": (1200, 288, 0, 0, 960),
            "retain_on_error": (528, 0, 384, 1152, 0),
            "quarantine": (624, 0, 288, 0, 0),
            "bounded_roles": (720, 0, 192, 0, 0),
        }
        for policy in get_args(Policy):
            with self.subTest(policy=policy):
                counts = Counter()
                for left, right, (init, finish, first_live, kind) in product(
                    permutations("abcd", 2), product("abcd", repeat=2), _OUTCOMES,
                ):
                    observed = receipt(init, finish)
                    self.assertEqual(observed.obligations, {Obligation("handle", kind)} if kind else set())
                    decision = consider(policy, BackupPair(*left), BackupPair(*right), observed)
                    allows = compatible(left, right, first_live)
                    claims_handle = any(item.kind in ("owned", "retained") for item in decision.output.obligations)
                    counts["inputs"] += 1
                    counts["admitted"] += decision.admits
                    counts["unsafe"] += decision.admits and not allows
                    counts["extra_blocks"] += not decision.admits and allows
                    counts["unsupported_claim"] += claims_handle and kind not in ("owned", "retained")
                    counts["lost_obligation"] += kind is not None and not decision.output.obligations
                self.assertEqual(counts["inputs"], 1728)
                columns = ("admitted", "unsafe", "extra_blocks", "unsupported_claim", "lost_obligation")
                self.assertEqual(tuple(counts[key] for key in columns), expected[policy])
