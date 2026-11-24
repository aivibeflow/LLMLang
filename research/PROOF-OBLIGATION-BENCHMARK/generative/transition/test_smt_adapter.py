import subprocess
import unittest
from unittest.mock import patch

from machine import Unsupported
from smt_adapter import control, experiment, outcome, solver_responses, state_query


class SmtAdapterTests(unittest.TestCase):
    def test_all_action_boundaries_are_observed(self):
        full = state_query(*control())
        weakened = state_query(*control(), final_only_control=True)
        self.assertIn("(define-fun r1 () Int (- 1))", full)
        self.assertIn("(distinct r1 0)", full)
        self.assertNotIn("(distinct r1 0)", weakened)
        self.assertIn("(distinct r2 0)", weakened)

    def test_observation_domain_is_checked(self):
        machine, initial, trace, expected = control()
        for args in [(machine, {"missing": 0}, trace, expected),
                     (machine, initial, [["change"]], expected),
                     (machine, initial, trace, [{"x": 0}, {"x": True}])]:
            with self.subTest(args=args), self.assertRaises(Unsupported):
                state_query(*args)

    def test_empty_trace_has_no_state_mismatch(self):
        machine, initial, _, _ = control()
        self.assertIn("(assert false)", state_query(machine, initial, [], []))

    def test_batch_order_is_stable(self):
        source, records = experiment()
        self.assertEqual(len(records), 800)
        self.assertEqual(source.count("(check-sat)"), len(records))
        self.assertEqual(records[-2]["control"], "all-boundaries")
        self.assertEqual(records[-1]["control"], "final-only")

    def test_unknown_and_conflicts_cannot_be_agreement(self):
        self.assertEqual(outcome("unknown", False), "abstain")
        self.assertEqual(outcome("sat", False), "translation-or-solver-conflict")
        self.assertEqual(outcome("unsat", True), "translation-or-solver-conflict")

    @patch("smt_adapter.subprocess.run")
    def test_solver_response_validation(self, run):
        for stdout, stderr, code, status in [
            ("unknown\n", "", 0, "ok"),
            ("sat\nunsat\n", "", 0, "invalid-response"),
            ("sat\n", "warning", 0, "invalid-response"),
            ("", "", 1, "invalid-response"),
            ("unsupported\n", "", 0, "invalid-response"),
        ]:
            with self.subTest(stdout=stdout, stderr=stderr, code=code):
                run.return_value = subprocess.CompletedProcess([], code, stdout, stderr)
                self.assertEqual(solver_responses("cvc5", "query", 1), (status, stdout, stderr))
        run.side_effect = subprocess.TimeoutExpired("cvc5", 30, output=b"sat\n")
        self.assertEqual(solver_responses("cvc5", "query", 1), ("timeout", "sat\n", ""))
        run.side_effect = FileNotFoundError("solver missing")
        self.assertEqual(solver_responses("cvc5", "query", 1),
                         ("unavailable", "", "solver missing"))


if __name__ == "__main__":
    unittest.main()
