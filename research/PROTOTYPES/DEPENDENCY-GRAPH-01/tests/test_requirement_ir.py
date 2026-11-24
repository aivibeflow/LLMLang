import unittest

from src.requirement_ir import (
    Action, BusinessRule, ComponentContract, Junction, Operator, Predicate,
    Requirement, RequirementIR, TemporalBound, Trigger, ValueType, Variable,
    analyze, generate_scenarios, validate_policy_boundary,
)


class RequirementIRTests(unittest.TestCase):
    def setUp(self):
        self.source_ids = frozenset({"intent:preferred-tax"})
        self.decision_ids = frozenset({"decision:order-date"})
        self.variables = (
            Variable("rate_basis_points", ValueType.INT, (1200, 1500, 2000)),
            Variable("order_date_day", ValueType.INT, (20261130, 20261201, 20261205)),
            Variable("caller", ValueType.TEXT, ("preferred_order", "standard_order")),
        )

    def test_typed_ir_retains_trigger_action_temporal_and_provenance(self):
        req = Requirement(
            "R-PREFERRED-RATE", "preferred_order", "preferred_order",
            Junction("and", (
                Predicate("rate_basis_points", Operator.EQ, 1200),
                Predicate("caller", Operator.EQ, "preferred_order"),
            )),
            ("intent:preferred-tax",), ("decision:order-date",),
            required_dimensions=("rate_basis_points",),
            trigger=Trigger("order_placed", Predicate(
                "order_date_day", Operator.GE, 20261201)),
            action=Action("select_policy", "calculate_tax",
                          (("input", "rate_basis_points"),)),
            temporal=TemporalBound("after", 0, "effective-date"),
        )
        ir = RequirementIR(self.variables, (req,), self.source_ids, self.decision_ids)
        result = analyze(ir)
        self.assertEqual(result.status, "FINITE_MODEL_CONSISTENT")
        self.assertEqual(req.trigger.event, "order_placed")
        self.assertEqual(req.action.operation, "select_policy")

    def test_contradictory_requirements_are_detected(self):
        first = Requirement("R1", "preferred_order", "preferred_order",
                            Predicate("rate_basis_points", Operator.EQ, 1200),
                            ("intent:preferred-tax",))
        second = Requirement("R2", "preferred_order", "preferred_order",
                             Predicate("rate_basis_points", Operator.EQ, 1500),
                             ("intent:preferred-tax",))
        ir = RequirementIR(self.variables, (first, second),
                           self.source_ids, self.decision_ids)
        result = analyze(ir)
        self.assertIn("CONTRADICTION", {issue.code for issue in result.issues})
        self.assertEqual(result.status, "NEEDS_REVIEW")

    def test_required_dimension_flags_underdetermination(self):
        req = Requirement("R1", "preferred_order", "preferred_order",
                          Predicate("caller", Operator.EQ, "preferred_order"),
                          ("intent:preferred-tax",),
                          required_dimensions=("rate_basis_points",))
        result = analyze(RequirementIR(self.variables, (req,),
                                       self.source_ids, self.decision_ids))
        self.assertIn("UNDERDETERMINED", {issue.code for issue in result.issues})

    def test_missing_provenance_is_reported(self):
        req = Requirement("R1", "preferred_order", "preferred_order",
                          Predicate("rate_basis_points", Operator.EQ, 1200),
                          ("missing-source",))
        result = analyze(RequirementIR(self.variables, (req,),
                                       self.source_ids, self.decision_ids))
        self.assertIn("DANGLING_PROVENANCE", {issue.code for issue in result.issues})

    def test_unresolved_and_assumptions_prevent_clean_acceptance(self):
        req = Requirement("R1", "preferred_order", "preferred_order",
                          Predicate("rate_basis_points", Operator.EQ, 1200),
                          ("intent:preferred-tax",),
                          assumptions=("rounding mode not confirmed",),
                          unresolved=("which date basis applies",))
        result = analyze(RequirementIR(self.variables, (req,),
                                       self.source_ids, self.decision_ids))
        codes = {issue.code for issue in result.issues}
        self.assertIn("ASSUMPTION", codes)
        self.assertIn("UNRESOLVED", codes)
        self.assertEqual(result.status, "NEEDS_REVIEW")

    def test_type_mismatch_is_rejected(self):
        req = Requirement("R1", "preferred_order", "preferred_order",
                          Predicate("rate_basis_points", Operator.EQ, "twelve percent"),
                          ("intent:preferred-tax",))
        result = analyze(RequirementIR(self.variables, (req,),
                                       self.source_ids, self.decision_ids))
        self.assertIn("TYPE_MISMATCH", {issue.code for issue in result.issues})
        self.assertEqual(result.status, "INVALID")

    def test_finite_scenarios_include_pass_and_counterexamples(self):
        req = Requirement("R1", "preferred_order", "preferred_order",
                          Predicate("rate_basis_points", Operator.EQ, 1200),
                          ("intent:preferred-tax",))
        scenarios = generate_scenarios(RequirementIR(
            self.variables, (req,), self.source_ids, self.decision_ids))
        self.assertTrue(any(s.satisfies for s in scenarios))
        self.assertTrue(any(not s.satisfies for s in scenarios))
        self.assertEqual(len(scenarios), 18)

    def test_analysis_bound_returns_unknown_not_success(self):
        req = Requirement("R1", "preferred_order", "preferred_order",
                          Predicate("rate_basis_points", Operator.EQ, 1200),
                          ("intent:preferred-tax",))
        result = analyze(RequirementIR(self.variables, (req,),
                                       self.source_ids, self.decision_ids),
                         max_assignments=2)
        self.assertEqual(result.status, "UNKNOWN")
        self.assertIn("ANALYSIS_BOUND_EXCEEDED",
                      {issue.code for issue in result.issues})

    def test_assignment_limit_distinguishes_unknown_from_completed_analysis(self):
        first = Requirement("R1", "preferred_order", "preferred_order",
                            Predicate("rate_basis_points", Operator.EQ, 1200),
                            ("intent:preferred-tax",))
        second = Requirement("R2", "preferred_order", "preferred_order",
                             Predicate("rate_basis_points", Operator.EQ, 1500),
                             ("intent:preferred-tax",))
        cases = {
            "satisfiable": ((first,), "FINITE_MODEL_CONSISTENT", 18, 6, set()),
            "contradictory": ((first, second), "NEEDS_REVIEW", 18, 0, {"CONTRADICTION"}),
            "no_requirements": ((), "FINITE_MODEL_CONSISTENT", 0, 0, set()),
        }
        for case, (requirements, status, count, satisfying, codes) in cases.items():
            ir = RequirementIR(self.variables, requirements, self.source_ids, self.decision_ids)
            for limit in (0, 17):
                with self.subTest(case=case, limit=limit):
                    result = analyze(ir, max_assignments=limit)
                    self.assertEqual(result.status, "UNKNOWN")
                    self.assertEqual({issue.code for issue in result.issues}, {"ANALYSIS_BOUND_EXCEEDED"})
                    self.assertEqual(result.scenarios, ())
                    self.assertEqual(generate_scenarios(ir, max_assignments=limit), ())
            for limit in (18, 19):
                with self.subTest(case=case, limit=limit):
                    result = analyze(ir, max_assignments=limit)
                    self.assertEqual(result.status, status)
                    self.assertEqual({issue.code for issue in result.issues}, codes)
                    self.assertEqual(len(result.scenarios), count)
                    self.assertEqual(sum(scenario.satisfies for scenario in result.scenarios), satisfying)
                    self.assertEqual(generate_scenarios(ir, max_assignments=limit), result.scenarios)

    def test_caller_policy_is_explicit_input_not_hidden_callee_rule(self):
        rule = BusinessRule("preferred-tax", "preferred_order", "preferred_order",
                            Predicate("rate_basis_points", Operator.EQ, 1200),
                            ("intent:preferred-tax",))
        caller = ComponentContract("preferred_order", "caller")
        callee = ComponentContract("calculate_tax", "callee",
                                   ("taxable_basis_cents", "rate_basis_points"))
        self.assertEqual(validate_policy_boundary(rule, caller, callee), ())

    def test_missing_policy_input_and_wrong_owner_are_reported(self):
        rule = BusinessRule("preferred-tax", "calculate_tax", "preferred_order",
                            Predicate("rate_basis_points", Operator.EQ, 1200),
                            ("intent:preferred-tax",))
        caller = ComponentContract("preferred_order", "caller")
        callee = ComponentContract("calculate_tax", "callee")
        codes = {issue.code for issue in validate_policy_boundary(rule, caller, callee)}
        self.assertIn("POLICY_OWNER_MISMATCH", codes)
        self.assertIn("HIDDEN_CALLEE_POLICY", codes)
        self.assertIn("MISSING_POLICY_INPUT", codes)


if __name__ == "__main__":
    unittest.main()
