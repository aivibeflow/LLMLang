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


def call_site(target_hash):
    return [{
        "call_site_id": "call:tax",
        "targets": [{
            "target_id": "direct",
            "target_hash": target_hash,
            "condition": None,
        }],
    }]


class CandidateCallSiteValidationTests(unittest.TestCase):
    def setUp(self):
        self.store = ContentStore()
        self.old_callee = publish_declaration(
            self.store, declaration("function", "fn:tax:v1", {"body": "old"})
        )
        self.new_callee = publish_declaration(
            self.store, declaration("function", "fn:tax:v2", {"body": "new"})
        )
        self.old_caller = publish_declaration(
            self.store, declaration(
                "function", "fn:invoice:v1", {"body": "invoice"},
                call_sites=call_site(self.old_callee),
            )
        )
        self.new_caller = publish_declaration(
            self.store, declaration(
                "function", "fn:invoice:v2", {"body": "invoice"},
                call_sites=call_site(self.new_callee),
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

    def test_candidate_call_target_must_match_selected_exact_callee(self):
        wrong_caller = publish_declaration(
            self.store, declaration(
                "function", "fn:invoice:wrong", {"body": "invoice"},
                call_sites=call_site(self.old_callee),
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

    def test_preserve_requires_original_caller_and_callee_versions(self):
        candidate = make_snapshot({
            "tax": self.old_callee,
            "invoice": self.old_caller,
        })
        result = validate_candidate_call_site_decisions(
            self.store, self.baseline, candidate,
            self.plan(
                disposition=CallSiteDisposition.PRESERVE,
                selected=self.old_callee,
                caller=self.old_caller,
                candidate=candidate,
            ),
        )
        self.assertTrue(result.valid, result.errors)

        invalid = validate_candidate_call_site_decisions(
            self.store, self.baseline, self.candidate,
            self.plan(
                disposition=CallSiteDisposition.PRESERVE,
                selected=self.old_callee,
                caller=self.new_caller,
            ),
        )
        self.assertFalse(invalid.valid)
        self.assertTrue(any("PRESERVE changed the exact caller" in error
                            for error in invalid.errors))

    def test_unresolved_decision_never_validates(self):
        decision = CallSiteDecision(
            self.old_caller, "call:tax", "direct", self.old_callee,
            CallSiteDisposition.UNRESOLVED, None, None,
            "not established", None,
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
