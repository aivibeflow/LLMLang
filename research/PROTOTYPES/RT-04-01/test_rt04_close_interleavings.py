"""Check the schedule space and the outcomes it distinguishes."""

from collections import Counter
from unittest import TestCase

from rt04_close_interleavings import Observation, Schedule, predict, schedules
from rt04_sqlite_recovery import BUSY, OK


class CloseInterleavingTests(TestCase):
    def test_single_prepare_in_each_available_gap(self):
        corpus = tuple(schedules())
        self.assertEqual(len(set(corpus)), len(corpus))
        counts = Counter((case.policy, predict(case).close_code) for case in corpus)
        self.assertEqual(counts, {
            ("split_snapshot", None): 1,
            ("split_snapshot", BUSY): 1,
            ("split_snapshot", OK): 1,
            ("split_version", None): 2,
            ("split_version", BUSY): 1,
            ("split_version", OK): 1,
            ("shared_guard", None): 1,
            ("shared_guard", OK): 1,
            ("alias_guard", None): 1,
            ("alias_guard", BUSY): 1,
        })

    def test_matching_version_leaves_a_gap_before_close(self):
        after_observation = Schedule("split_version", "after_snapshot")
        after_validation = Schedule("split_version", "after_validation")
        self.assertEqual(predict(after_observation), Observation(0, False, None, True))
        self.assertEqual(predict(after_validation), Observation(0, True, BUSY, True))

    def test_shared_guard_orders_prepare_with_close_and_checks_retirement(self):
        earlier = Schedule("shared_guard", "before_snapshot")
        later = Schedule("shared_guard", "after_close")
        self.assertEqual(predict(earlier), Observation(1, None, None, True))
        self.assertEqual(predict(later), Observation(0, None, OK, False))

    def test_other_lock_leaves_the_same_handle_mutable(self):
        schedule = Schedule("alias_guard", "after_snapshot")
        self.assertEqual(predict(schedule), Observation(0, None, BUSY, True))
