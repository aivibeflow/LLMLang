import unittest

from rt03_bounded_solver_worker import run_pigeonhole_query
from rt03_feasibility_outcomes import (
    SolverAnswer,
    Verdict,
    classify_solver_answer,
    retain_as_possible,
)


class BoundedSolverWorkerTests(unittest.TestCase):
    def test_sat_query_returns_replayable_pigeonhole_assignment(self):
        result = run_pigeonhole_query(2, 2, timeout_seconds=2)
        self.assertEqual(result.status, "sat")
        self.assertIsNone(result.reason)
        self.assertEqual(set(result.model), {
            "p0_h0", "p0_h1", "p1_h0", "p1_h1",
        })
        self.assertEqual(sum(result.model.values()), 2)
        self.assertTrue(result.worker_reaped)

    def test_small_unsat_query_completes_but_untrusted_unsat_is_not_pruning_evidence(self):
        result = run_pigeonhole_query(3, 2, timeout_seconds=2)
        self.assertEqual(result.status, "unsat")
        self.assertIsNone(result.reason)
        self.assertTrue(result.worker_reaped)
        verdict = classify_solver_answer(
            SolverAnswer(result.status, reason=result.reason), (), frozenset()
        )
        self.assertIs(verdict, Verdict.UNKNOWN)
        self.assertTrue(retain_as_possible(verdict))

    def test_hard_unsat_query_hits_real_worker_deadline_and_is_reaped(self):
        result = run_pigeonhole_query(12, 11, timeout_seconds=0.5)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason, "timeout")
        self.assertGreaterEqual(result.query_seconds, 0.5)
        self.assertTrue(result.worker_reaped)
        self.assertIsNone(result.model)
        verdict = classify_solver_answer(
            SolverAnswer(result.status, reason=result.reason), (), frozenset()
        )
        self.assertIs(verdict, Verdict.UNKNOWN)
        self.assertTrue(retain_as_possible(verdict))

    def test_nonpositive_timeout_is_rejected_before_spawning(self):
        with self.assertRaises(ValueError):
            run_pigeonhole_query(2, 2, timeout_seconds=0)


if __name__ == "__main__":
    unittest.main()
