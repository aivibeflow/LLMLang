import unittest

from src.requirement_evolution import (
    analyze_impact, create_derived_artifact, create_requirement_state,
    make_verification_key, merge_requirement_branches, merge_selections,
    record_lineage, split_selection,
)
from src.semantic_graph import ContentStore, RelationStore, make_snapshot


class RequirementEvolutionTests(unittest.TestCase):
    def setUp(self):
        self.store = ContentStore()
        self.relations = RelationStore()

        self.preferred_v1 = create_requirement_state(
            self.store, "preferred-tax",
            {"rate_basis_points": 1500, "date_basis": "order_date"})
        self.standard_v1 = create_requirement_state(
            self.store, "standard-tax",
            {"rate_basis_points": 2000, "date_basis": "order_date"})

        self.preferred_clause_v1 = create_derived_artifact(
            self.store, "formal_clause", {"predicate": "rate == 1500"},
            (("requirement", self.preferred_v1),))
        self.preferred_contract_v1 = create_derived_artifact(
            self.store, "caller_contract", {"caller": "preferred_order"},
            (("formal_clause", self.preferred_clause_v1),))
        self.preferred_tests_v1 = create_derived_artifact(
            self.store, "test_suite", {"cases": ["before", "boundary"]},
            (("contract", self.preferred_contract_v1),))
        self.preferred_verification_v1 = create_derived_artifact(
            self.store, "verification_record", {"status": "PROVEN"},
            (("contract", self.preferred_contract_v1),
             ("tests", self.preferred_tests_v1)))

        self.standard_contract = create_derived_artifact(
            self.store, "caller_contract", {"caller": "standard_order"},
            (("requirement", self.standard_v1),))
        self.tax_callee_contract = self.store.put(
            "callee_contract",
            {"function": "calculate_tax",
             "inputs": ["taxable_basis_cents", "rate_basis_points"]})

        self.base = make_snapshot({
            "requirement:preferred-tax": self.preferred_v1,
            "requirement:standard-tax": self.standard_v1,
            "clause:preferred-tax": self.preferred_clause_v1,
            "contract:preferred-order": self.preferred_contract_v1,
            "tests:preferred-order": self.preferred_tests_v1,
            "verification:preferred-order": self.preferred_verification_v1,
            "contract:standard-order": self.standard_contract,
            "contract:calculate-tax": self.tax_callee_contract,
        })

    def test_snapshot_selection_key_is_not_part_of_semantic_content_hash(self):
        same_content_other_key = create_requirement_state(
            self.store, "a-different-snapshot-slot",
            {"rate_basis_points": 1500, "date_basis": "order_date"})
        self.assertEqual(same_content_other_key, self.preferred_v1)

    def test_semantic_change_impacts_only_dependent_caller_chain(self):
        preferred_v2 = create_requirement_state(
            self.store, "preferred-tax",
            {"rate_basis_points": 1200, "date_basis": "order_date"})
        clause_v2 = create_derived_artifact(
            self.store, "formal_clause", {"predicate": "rate == 1200"},
            (("requirement", preferred_v2),))
        contract_v2 = create_derived_artifact(
            self.store, "caller_contract", {"caller": "preferred_order"},
            (("formal_clause", clause_v2),))
        tests_v2 = create_derived_artifact(
            self.store, "test_suite", {"cases": ["before", "boundary", "after"]},
            (("contract", contract_v2),))
        verification_v2 = create_derived_artifact(
            self.store, "verification_record", {"status": "NOT_CHECKED"},
            (("contract", contract_v2), ("tests", tests_v2)))
        candidate = make_snapshot({
            "requirement:preferred-tax": preferred_v2,
            "requirement:standard-tax": self.standard_v1,
            "clause:preferred-tax": clause_v2,
            "contract:preferred-order": contract_v2,
            "tests:preferred-order": tests_v2,
            "verification:preferred-order": verification_v2,
            "contract:standard-order": self.standard_contract,
            "contract:calculate-tax": self.tax_callee_contract,
        }, (self.base.root_hash,))

        report = analyze_impact(self.store, self.preferred_v1, preferred_v2,
                                self.base, candidate)
        impacted_kinds = {self.store.get(h).kind
                          for h in report.active_baseline_dependents}
        self.assertTrue(report.changed)
        self.assertEqual(impacted_kinds,
                         {"formal_clause", "caller_contract", "test_suite",
                          "verification_record"})
        self.assertNotIn(self.standard_contract, report.transitive_dependents)
        self.assertNotIn(self.tax_callee_contract, report.transitive_dependents)
        self.assertEqual(report.changed_selection_keys, (
            "clause:preferred-tax", "contract:preferred-order",
            "requirement:preferred-tax", "tests:preferred-order",
            "verification:preferred-order"))

    def test_provenance_only_change_does_not_change_semantic_hash_or_verification_key(self):
        same_state = create_requirement_state(
            self.store, "preferred-tax",
            {"rate_basis_points": 1500, "date_basis": "order_date"})
        record_lineage(self.relations, "project-A", self.preferred_v1,
                       "rephrases", same_state)
        key_before = make_verification_key(
            self.store, self.preferred_contract_v1, "checker-v1", {"mode": "strict"})
        key_after = make_verification_key(
            self.store, self.preferred_contract_v1, "checker-v1", {"mode": "strict"})
        self.assertEqual(same_state, self.preferred_v1)
        self.assertEqual(key_before, key_after)
        self.assertEqual(len(self.relations.for_scope("project-A")), 1)

    def test_semantic_change_invalidates_verification_identity(self):
        changed = create_requirement_state(
            self.store, "preferred-tax",
            {"rate_basis_points": 1200, "date_basis": "order_date"})
        clause = create_derived_artifact(
            self.store, "formal_clause", {"predicate": "rate == 1200"},
            (("requirement", changed),))
        contract = create_derived_artifact(
            self.store, "caller_contract", {"caller": "preferred_order"},
            (("formal_clause", clause),))
        old_key = make_verification_key(
            self.store, self.preferred_contract_v1, "checker-v1", {"mode": "strict"})
        new_key = make_verification_key(
            self.store, contract, "checker-v1", {"mode": "strict"})
        self.assertNotEqual(old_key, new_key)

    def test_split_records_lineage_without_hashing_it_into_children(self):
        child_a = create_requirement_state(self.store, "preferred-tax-base",
                                           {"rate_basis_points": 1200})
        child_b = create_requirement_state(self.store, "preferred-tax-date",
                                           {"date_basis": "order_date"})
        record_lineage(self.relations, "project-A", self.preferred_v1,
                       "split_into", child_a)
        record_lineage(self.relations, "project-A", self.preferred_v1,
                       "split_into", child_b)
        split = split_selection(self.base, "requirement:preferred-tax", {
            "requirement:preferred-tax-base": child_a,
            "requirement:preferred-tax-date": child_b,
        })
        self.assertNotIn("requirement:preferred-tax", split.mapping)
        self.assertIn("requirement:preferred-tax-base", split.mapping)
        self.assertEqual(len(self.relations.for_scope("project-A")), 2)

    def test_merge_records_lineage_and_creates_new_selection(self):
        req_a = create_requirement_state(self.store, "tax-rate",
                                         {"rate_basis_points": 1200})
        req_b = create_requirement_state(self.store, "tax-date",
                                         {"date_basis": "order_date"})
        merged_value = create_requirement_state(
            self.store, "preferred-tax",
            {"rate_basis_points": 1200, "date_basis": "order_date"})
        record_lineage(self.relations, "project-A", req_a, "merged_from", merged_value)
        record_lineage(self.relations, "project-A", req_b, "merged_from", merged_value)
        start = make_snapshot({"requirement:tax-rate": req_a,
                               "requirement:tax-date": req_b})
        merged = merge_selections(start, ("requirement:tax-rate",
                                           "requirement:tax-date"),
                                  "requirement:preferred-tax", merged_value)
        self.assertEqual(merged.mapping, {"requirement:preferred-tax": merged_value})

    def test_disjoint_requirement_edits_merge(self):
        base = make_snapshot({"req:preferred": "p0", "req:standard": "s0"})
        left = make_snapshot({"req:preferred": "p1", "req:standard": "s0"},
                             (base.root_hash,))
        right = make_snapshot({"req:preferred": "p0", "req:standard": "s1"},
                              (base.root_hash,))
        report = merge_requirement_branches(base, left, right)
        self.assertEqual(report.conflicts, ())
        self.assertEqual(report.snapshot.mapping,
                         {"req:preferred": "p1", "req:standard": "s1"})

    def test_concurrent_edits_to_same_requirement_conflict(self):
        base = make_snapshot({"req:preferred": "p0"})
        left = make_snapshot({"req:preferred": "p1"}, (base.root_hash,))
        right = make_snapshot({"req:preferred": "p2"}, (base.root_hash,))
        report = merge_requirement_branches(base, left, right)
        self.assertIsNone(report.snapshot)
        self.assertEqual(report.conflicts, (("req:preferred", "p1", "p2"),))

    def test_lineage_is_not_an_allowed_semantic_dependency_shortcut(self):
        with self.assertRaises(ValueError):
            record_lineage(self.relations, "project-A", self.preferred_v1,
                           "depends_on", self.standard_v1)


if __name__ == "__main__":
    unittest.main()
