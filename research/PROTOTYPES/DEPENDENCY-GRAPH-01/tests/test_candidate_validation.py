import unittest

from src.candidate_validation import validate_candidate_call_site_decisions
from src.impact_planning import CallSiteDecision, CallSiteDisposition, ImpactPlan
from src.semantic_dependency_index import FORMAT, SCHEMA_VERSION, publish_declaration
from src.semantic_graph import ContentStore, make_snapshot


def declaration(kind, declaration_id, content=None, **extra):
    return {
        "format": FORMAT,
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "declaration_id": declaration_id,
        "content": content or {},
        **extra,
    }


def call_site(target_hash, required_contract_hash):
    return [{
        "call_site_id": "call:tax",
        "targets": [{
            "target_id": "direct",
            "target_hash": target_hash,
            "condition": None,
            "required_contract_hash": required_contract_hash,
        }],
    }]


class CandidateCallSiteValidationTests(unittest.TestCase):
    def setUp(self):
        self.store = ContentStore()
        self.contract_hash = publish_declaration(
            self.store, declaration("contract", "contract:tax", {"name": "TaxContract"})
        )
        provided = [{"reference_id": "provided-contract", "relation": "provides_contract",
                     "target_hash": self.contract_hash, "target_kind": "contract"}]
        self.old_callee = publish_declaration(
            self.store, declaration("function", "fn:tax:v1", {"body": "old"},
                                    references=provided)
        )
        self.new_callee = publish_declaration(
            self.store, declaration("function", "fn:tax:v2", {"body": "new"},
                                    references=provided)
        )
        self.old_caller = publish_declaration(
            self.store, declaration(
                "function", "fn:invoice:v1", {"body": "invoice"},
                call_sites=call_site(self.old_callee, self.contract_hash),
            )
        )
        self.new_caller = publish_declaration(
            self.store, declaration(
                "function", "fn:invoice:v2", {"body": "invoice"},
                call_sites=call_site(self.new_callee, self.contract_hash),
            )
        )
        self.baseline = make_snapshot({
            "tax": self.old_callee,
            "invoice": self.old_caller,
        })
        self.candidate = make_snapshot({
            "tax": self.new_callee,
            "invoice": self.new_caller,
        })

    def plan(self, disposition=CallSiteDisposition.MIGRATE,
             selected=None, caller=None, candidate=None):
        selected = self.new_callee if selected is None else selected
        caller = self.new_caller if caller is None else caller
        candidate = self.candidate if candidate is None else candidate
        decision = CallSiteDecision(
            caller_hash=self.old_caller,
            call_site_id="call:tax",
            target_id="direct",
            base_callee_hash=self.old_callee,
            disposition=disposition,
            selected_callee_hash=selected,
            resulting_caller_hash=caller,
            rationale="candidate behavior is required",
            decision_evidence_id="compatibility-evidence:001",
            required_contract_hash=self.contract_hash,
            compatibility_status="PROVEN",
        )
        return ImpactPlan(
            plan_id="plan:001",
            baseline_root=self.baseline.root_hash,
            candidate_root=candidate.root_hash,
            policy_id="policy:001",
            actions=(),
            audit_statuses=(),
            call_site_decisions=(decision,),
        )

    def test_migration_is_validated_against_materialized_candidate(self):
        result = validate_candidate_call_site_decisions(
            self.store, self.baseline, self.candidate, self.plan()
        )
        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.checked_decisions, 1)

    def test_adapt_and_fork_require_materialized_caller_versions(self):
        for disposition in (CallSiteDisposition.ADAPT, CallSiteDisposition.FORK):
            with self.subTest(disposition=disposition):
                result = validate_candidate_call_site_decisions(
                    self.store, self.baseline, self.candidate,
                    self.plan(disposition=disposition),
                )
                self.assertTrue(result.valid, result.errors)

    def test_candidate_call_target_must_match_selected_exact_callee(self):
        wrong_caller = publish_declaration(
            self.store, declaration(
                "function", "fn:invoice:wrong", {"body": "invoice"},
                call_sites=call_site(self.old_callee, self.contract_hash),
            )
        )
        wrong_candidate = make_snapshot({
            "tax": self.new_callee,
            "invoice": wrong_caller,
        })
        result = validate_candidate_call_site_decisions(
            self.store, self.baseline, wrong_candidate,
            self.plan(caller=wrong_caller, candidate=wrong_candidate),
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("not selected callee" in error for error in result.errors))

    def test_selected_callee_must_be_selected_by_candidate_snapshot(self):
        result = validate_candidate_call_site_decisions(
            self.store, self.baseline, self.baseline,
            self.plan(selected=self.new_callee, caller=self.old_caller,
                      candidate=self.baseline),
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("selected callee is not selected" in error
                            for error in result.errors))

    def test_preserve_keeps_exact_callee_when_caller_is_revised_for_other_changes(self):
        revised_caller = publish_declaration(
            self.store, declaration(
                "function", "fn:invoice:v2-preserving", {"body": "invoice plus other change"},
                call_sites=call_site(self.old_callee, self.contract_hash),
            )
        )
        candidate = make_snapshot({
            "tax": self.old_callee,
            "invoice": revised_caller,
        })
        result = validate_candidate_call_site_decisions(
            self.store, self.baseline, candidate,
            self.plan(
                disposition=CallSiteDisposition.PRESERVE,
                selected=self.old_callee,
                caller=revised_caller,
                candidate=candidate,
            ),
        )
        self.assertTrue(result.valid, result.errors)
    def test_one_caller_can_migrate_one_site_and_preserve_another(self):
        legacy_callee = publish_declaration(
            self.store, declaration("function", "fn:legacy:v1", {"body": "legacy"},
                references=[{"reference_id": "provided-contract", "relation": "provides_contract",
                             "target_hash": self.contract_hash, "target_kind": "contract"}])
        )
        base_caller = publish_declaration(
            self.store, declaration(
                "function", "fn:multi:v1", {"body": "multi"},
                call_sites=[
                    {"call_site_id": "call:new", "targets": [
                        {"target_id": "direct", "target_hash": self.old_callee, "condition": None, "required_contract_hash": self.contract_hash}]},
                    {"call_site_id": "call:legacy", "targets": [
                        {"target_id": "direct", "target_hash": legacy_callee, "condition": None, "required_contract_hash": self.contract_hash}]},
                ],
            )
        )
        revised_caller = publish_declaration(
            self.store, declaration(
                "function", "fn:multi:v2", {"body": "multi revised"},
                call_sites=[
                    {"call_site_id": "call:new", "targets": [
                        {"target_id": "direct", "target_hash": self.new_callee, "condition": None, "required_contract_hash": self.contract_hash}]},
                    {"call_site_id": "call:legacy", "targets": [
                        {"target_id": "direct", "target_hash": legacy_callee, "condition": None, "required_contract_hash": self.contract_hash}]},
                ],
            )
        )
        baseline = make_snapshot({
            "tax": self.old_callee,
            "legacy": legacy_callee,
            "multi": base_caller,
        })
        candidate = make_snapshot({
            "tax": self.new_callee,
            "legacy": legacy_callee,
            "multi": revised_caller,
        })
        decisions = (
            CallSiteDecision(
                base_caller, "call:new", "direct", self.old_callee,
                CallSiteDisposition.MIGRATE, self.new_callee, revised_caller,
                "new tax behavior required", "evidence:migrate",
                self.contract_hash, "PROVEN",
            ),
            CallSiteDecision(
                base_caller, "call:legacy", "direct", legacy_callee,
                CallSiteDisposition.PRESERVE, legacy_callee, revised_caller,
                "legacy behavior remains required", "evidence:preserve",
                self.contract_hash, "PROVEN",
            ),
        )
        plan = ImpactPlan(
            "plan:mixed-sites", baseline.root_hash, candidate.root_hash,
            "policy", (), (), (), decisions,
        )
        result = validate_candidate_call_site_decisions(
            self.store, baseline, candidate, plan
        )
        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.checked_decisions, 2)

    def test_unresolved_decision_never_validates(self):
        decision = CallSiteDecision(
            self.old_caller, "call:tax", "direct", self.old_callee,
            CallSiteDisposition.UNRESOLVED, None, None,
            "not established", None,
            self.contract_hash, None,
        )
        plan = ImpactPlan(
            "plan:unresolved", self.baseline.root_hash, self.candidate.root_hash,
            "policy", (), (), (), (decision,),
        )
        result = validate_candidate_call_site_decisions(
            self.store, self.baseline, self.candidate, plan
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("unresolved decision" in error for error in result.errors))

    def test_decision_must_match_actual_baseline_call_target(self):
        from dataclasses import replace

        baseline = make_snapshot({
            "tax-v1": self.old_callee,
            "tax-v2": self.new_callee,
            "invoice": self.old_caller,
        })
        decision = replace(
            self.plan().call_site_decisions[0],
            base_callee_hash=self.new_callee,
        )
        plan = ImpactPlan(
            "plan:wrong-base-edge", baseline.root_hash, self.candidate.root_hash,
            "policy", (), (), (), (decision,),
        )
        result = validate_candidate_call_site_decisions(
            self.store, baseline, self.candidate, plan
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("does not reference the decision's exact base callee"
                            in error for error in result.errors))

    def test_candidate_cannot_silently_change_call_site_requirement(self):
        alternate_contract = publish_declaration(
            self.store, declaration("contract", "contract:alternate", {"name": "Alternate"})
        )
        changed_caller = publish_declaration(
            self.store, declaration(
                "function", "fn:invoice:changed-requirement", {"body": "invoice"},
                call_sites=call_site(self.new_callee, alternate_contract),
            )
        )
        candidate = make_snapshot({
            "tax": self.new_callee,
            "invoice": changed_caller,
        })
        result = validate_candidate_call_site_decisions(
            self.store, self.baseline, candidate,
            self.plan(caller=changed_caller, candidate=candidate),
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("CIP-bound required contract" in error
                            for error in result.errors))

    def test_preserve_resolves_provided_contract_through_callee(self):
        plan = self.plan(
            disposition=CallSiteDisposition.PRESERVE,
            selected=self.old_callee, caller=self.old_caller,
            candidate=self.baseline,
        )
        result = validate_candidate_call_site_decisions(
            self.store, self.baseline, self.baseline, plan
        )
        self.assertTrue(result.valid, result.errors)

    def test_candidate_snapshot_root_is_bound_to_plan(self):
        wrong_plan = ImpactPlan(
            "plan:wrong-root", self.baseline.root_hash, "not-the-candidate-root",
            "policy", (), (), (), self.plan().call_site_decisions,
        )
        result = validate_candidate_call_site_decisions(
            self.store, self.baseline, self.candidate, wrong_plan
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("candidate root" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()
