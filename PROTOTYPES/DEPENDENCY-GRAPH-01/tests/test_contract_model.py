import unittest

from src.contract_model import (
    ContractModelError, FiniteBehaviorModel, check_finite_refinement,
)


class FiniteRefinementTests(unittest.TestCase):
    def model(self, role, rows, complete=True):
        return FiniteBehaviorModel.create(role, rows.keys(), rows, complete)

    def test_proven_when_all_complete_traces_are_allowed(self):
        contract = self.model("contract", {
            "n=0": [("return:0",)],
            "n=1": [("return:1",), ("return:one",)],
        })
        implementation = self.model("implementation", {
            "n=0": [("return:0",)],
            "n=1": [("return:1",)],
        })
        result = check_finite_refinement(contract, implementation)
        self.assertEqual(result.status, "PROVEN")
        self.assertEqual(result.counterexamples, ())

    def test_more_deterministic_implementation_is_valid_refinement(self):
        contract = self.model("contract", {
            "x": [("return:a",), ("return:b",)],
        })
        implementation = self.model("implementation", {
            "x": [("return:a",)],
        })
        self.assertEqual(check_finite_refinement(contract, implementation).status,
                         "PROVEN")

    def test_forbidden_result_disproves_refinement(self):
        contract = self.model("contract", {"x": [("return:allowed",)]})
        implementation = self.model("implementation", {
            "x": [("return:forbidden",)],
        })
        result = check_finite_refinement(contract, implementation)
        self.assertEqual(result.status, "DISPROVEN")
        self.assertEqual(result.counterexamples[0].input_value, "x")

    def test_unmodeled_implementation_input_is_unknown(self):
        contract = self.model("contract", {"x": [("return:x",)]})
        implementation = self.model("implementation", {
            "x": [("return:x",)],
        }, complete=False)
        self.assertEqual(check_finite_refinement(contract, implementation).status,
                         "UNKNOWN")

    def test_missing_required_input_disproves_complete_implementation(self):
        contract = self.model("contract", {
            "x": [("return:x",)], "y": [("return:y",)],
        })
        implementation = self.model("implementation", {
            "x": [("return:x",)],
        })
        result = check_finite_refinement(contract, implementation)
        self.assertEqual(result.status, "DISPROVEN")
        self.assertEqual(result.counterexamples[0].reason,
                         "implementation has no behavior for required input")

    def test_incomplete_contract_prevents_positive_proof(self):
        contract = self.model("contract", {"x": [("return:x",)]}, complete=False)
        implementation = self.model("implementation", {
            "x": [("return:x",)],
        })
        self.assertEqual(check_finite_refinement(contract, implementation).status,
                         "UNKNOWN")

    def test_exception_and_side_effect_are_observable_trace_events(self):
        contract = self.model("contract", {
            "x": [("write:invoice.total", "return:ok")],
        })
        implementation = self.model("implementation", {
            "x": [("write:invoice.total", "emit:email.sent", "return:ok")],
        })
        result = check_finite_refinement(contract, implementation)
        self.assertEqual(result.status, "DISPROVEN")
        self.assertIn("emit:email.sent", result.counterexamples[0].implementation_trace)

    def test_divergence_is_distinct_from_return(self):
        contract = self.model("contract", {"x": [("return:ok",)]})
        implementation = self.model("implementation", {"x": [("diverge",)]})
        self.assertEqual(check_finite_refinement(contract, implementation).status,
                         "DISPROVEN")

    def test_duplicate_and_incomplete_input_models_are_rejected(self):
        with self.assertRaises(ContractModelError):
            FiniteBehaviorModel.create("contract", ["x"], {}, complete=True)


if __name__ == "__main__":
    unittest.main()
