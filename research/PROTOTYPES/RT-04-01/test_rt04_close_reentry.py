"""Check callback decisions and the coverage of close observations."""

from collections import Counter
from unittest import TestCase

from rt04_close_reentry import (
    CallbackCase, CallbackObservation, CoverageObservation, callback_cases, coverage_cases,
    predict_callback, predict_coverage,
)
from rt04_sqlite_recovery import BUSY, OK


class CloseReentryTests(TestCase):
    def test_callback_corpus(self):
        cases = tuple(callback_cases())
        self.assertEqual(len(cases), len(set(cases)))
        counts = Counter((case.policy, predict_callback(case).close_code) for case in cases)
        self.assertEqual(counts, {
            ("lock_only", None): 2, ("lock_only", OK): 1, ("lock_only", BUSY): 1,
            ("reserve_close", None): 2, ("reserve_close", OK): 2,
            ("inspect_again", None): 3, ("inspect_again", OK): 1,
        })

    def test_mutation_can_be_refused_or_observed_before_close(self):
        cases = {
            "lock_only": CallbackObservation(0, "retained", 1, BUSY),
            "reserve_close": CallbackObservation(0, "refused", 0, OK),
            "inspect_again": CallbackObservation(0, "retained", 1, None),
        }
        for policy, expected in cases.items():
            with self.subTest(policy=policy):
                self.assertEqual(predict_callback(CallbackCase(policy, False, True)), expected)

    def test_live_dependency_blocks_entry_before_callback(self):
        for case in callback_cases():
            if case.initially_live:
                with self.subTest(case=case):
                    self.assertEqual(predict_callback(case), CallbackObservation(1, "skipped", 1, None))

    def test_empty_statement_view_misses_an_active_backup(self):
        self.assertEqual(predict_coverage("none", "close"), CoverageObservation(0, OK, True, True))
        self.assertEqual(predict_coverage("backup", "close"), CoverageObservation(0, BUSY, False, False))
        self.assertEqual(predict_coverage("blob", "close"), CoverageObservation(1, BUSY, False, False))

    def test_deferred_destruction_follows_each_dependent_release(self):
        corpus = tuple(coverage_cases())
        self.assertEqual(len(corpus), 8)
        for dependent, operation in corpus:
            with self.subTest(dependent=dependent, operation=operation):
                outcome = predict_coverage(dependent, operation)
                if dependent == "none":
                    self.assertEqual(outcome, CoverageObservation(0, OK, True, True))
                else:
                    self.assertFalse(outcome.destroyed_at_close)
                    self.assertEqual(outcome.destroyed_after_release, operation == "close_v2")
