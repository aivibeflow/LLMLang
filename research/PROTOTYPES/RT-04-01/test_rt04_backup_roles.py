"""Check concrete-identity coverage and the bounded reservation schedules."""

from collections import Counter
from itertools import permutations, product
from typing import get_args
from unittest import TestCase

from rt04_backup_roles import BackupPair, InitPlan, Policy, Stage, explore, permits, resolve


class BackupRoleTests(TestCase):
    def test_shared_source_and_exclusive_destination(self):
        first = BackupPair("A", "B")
        self.assertTrue(permits((first,), BackupPair("A", "C")))
        self.assertFalse(permits((first,), BackupPair("C", "B")))
        self.assertFalse(permits((first,), BackupPair("C", "A")))
        self.assertFalse(permits((first,), BackupPair("B", "C")))
        self.assertFalse(permits((), BackupPair("A", "A")))

    def test_binding_names_miss_self_aliases_and_role_conflicts(self):
        identities = {f"{item}{suffix}": item for item, suffix in product("ABC", "01")}
        pairs = tuple(BackupPair(*items) for items in product(identities, repeat=2))
        false_admissions = sum(permits((), pair) and not permits((), resolve(pair, identities)) for pair in pairs)
        self.assertEqual(false_admissions, 6)
        outcomes = Counter()
        for first, second in product(pairs, repeat=2):
            live = resolve(first, identities)
            if permits((), live):
                candidate = resolve(second, identities)
                by_name = permits((first,), second)
                by_identity = permits((live,), candidate)
                same_resource = candidate.source == candidate.destination
                outcomes[by_name, by_identity, same_resource] += 1
        self.assertEqual(outcomes, {
            (False, False, True): 216, (True, False, True): 72,
            (False, False, False): 264, (True, False, False): 216,
            (True, True, False): 96,
        })

    def test_reversed_role_order_can_deadlock_before_init(self):
        first = InitPlan(BackupPair("A", "B"), True)
        second = InitPlan(BackupPair("B", "A"), False)
        report = explore("role_order", first, second)
        self.assertEqual(report.deadlocks, {(Stage.FIRST_HELD, Stage.FIRST_HELD)})
        self.assertIn((Stage.DONE, Stage.DONE), report.reachable)

    def test_failed_init_releases_both_reservations_for_a_waiter(self):
        failed = InitPlan(BackupPair("A", "B"), False)
        waiter = InitPlan(BackupPair("B", "A"), True)
        for policy in ("identity_order", "all_or_none"):
            with self.subTest(policy=policy):
                report = explore(policy, failed, waiter)
                self.assertIn((Stage.RESERVED, Stage.READY), report.reachable)
                self.assertIn((Stage.DONE, Stage.ACTIVE), report.reachable)
                self.assertNotIn((Stage.ACTIVE, Stage.READY), report.reachable)
                self.assertFalse(report.deadlocks)

    def test_all_reservation_plans(self):
        pairs = tuple(BackupPair(*items) for items in permutations("ABC", 2))
        plans = tuple(InitPlan(pair, succeeds) for pair, succeeds in product(pairs, (False, True)))
        expected = (("role_order", 24, 2502), ("identity_order", 0, 2370), ("all_or_none", 0, 1494))
        for policy, deadlocks, count in expected:
            with self.subTest(policy=policy):
                reports = tuple(explore(policy, *items) for items in product(plans, repeat=2))
                self.assertEqual(len(reports), 144)
                self.assertEqual(sum(bool(report.deadlocks) for report in reports), deadlocks)
                self.assertEqual(sum(len(report.reachable) for report in reports), count)
                self.assertTrue(all((Stage.DONE, Stage.DONE) in report.reachable for report in reports))
                partial = any(Stage.FIRST_HELD in state for report in reports for state in report.reachable)
                self.assertEqual(partial, policy != "all_or_none")
