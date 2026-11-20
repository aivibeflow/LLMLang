import unittest

from rt03_feasibility_outcomes import (
    SolverAnswer,
    Verdict,
    classify_solver_answer,
    retain_as_possible,
)


class FeasibilityOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.variables = frozenset({"x", "y"})
        self.route = ({"bool_var": "x"}, {"bool_not": {"bool_var": "y"}})

    def test_replayed_model_proves_feasible(self):
        answer = SolverAnswer("sat", {"x": True, "y": False})
        verdict = classify_solver_answer(answer, self.route, self.variables)
        self.assertIs(verdict, Verdict.FEASIBLE)
        self.assertTrue(retain_as_possible(verdict))

    def test_unknown_with_replayed_candidate_model_proves_feasible(self):
        answer = SolverAnswer(
            "unknown", {"x": True, "y": False}, reason="resource limit"
        )
        verdict = classify_solver_answer(answer, self.route, self.variables)
        self.assertIs(verdict, Verdict.FEASIBLE)

    def test_unreplayable_or_incomplete_model_is_unknown_and_retained(self):
        answers = (
            SolverAnswer("sat", {"x": True, "y": True}),
            SolverAnswer("sat", {"x": True}),
            SolverAnswer("sat", {"x": 1, "y": False}),
        )
        for answer in answers:
            with self.subTest(answer=answer):
                verdict = classify_solver_answer(answer, self.route, self.variables)
                self.assertIs(verdict, Verdict.UNKNOWN)
                self.assertTrue(retain_as_possible(verdict))

    def test_timeout_unknown_is_retained(self):
        answer = SolverAnswer("unknown", reason="timeout")
        verdict = classify_solver_answer(answer, self.route, self.variables)
        self.assertIs(verdict, Verdict.UNKNOWN)
        self.assertTrue(retain_as_possible(verdict))

    def test_untrusted_unsat_is_unknown_and_retained(self):
        answer = SolverAnswer("unsat", unsat_basis=None)
        verdict = classify_solver_answer(answer, self.route, self.variables)
        self.assertIs(verdict, Verdict.UNKNOWN)
        self.assertTrue(retain_as_possible(verdict))

    def test_stale_or_contradictory_models_are_ignored(self):
        for status in ("unsat", "error"):
            with self.subTest(status=status):
                answer = SolverAnswer(status, {"x": True, "y": False})
                verdict = classify_solver_answer(answer, self.route, self.variables)
                self.assertIs(verdict, Verdict.UNKNOWN)
                self.assertTrue(retain_as_possible(verdict))

    def test_explicit_unsat_evidence_can_prune(self):
        for basis in ("trusted_backend", "checked_certificate", "exact_finite_oracle"):
            with self.subTest(basis=basis):
                answer = SolverAnswer("unsat", unsat_basis=basis)
                verdict = classify_solver_answer(answer, self.route, self.variables)
                self.assertIs(verdict, Verdict.INFEASIBLE)
                self.assertFalse(retain_as_possible(verdict))

    def test_solver_error_or_unknown_status_is_never_treated_as_unsat(self):
        for status in ("error", "cancelled", "unsupported", "unexpected"):
            with self.subTest(status=status):
                answer = SolverAnswer(status, reason="backend failure")
                verdict = classify_solver_answer(answer, self.route, self.variables)
                self.assertIs(verdict, Verdict.UNKNOWN)
                self.assertTrue(retain_as_possible(verdict))


if __name__ == "__main__":
    unittest.main()
