import hashlib
import json
import unittest

from src.candidate_semantic_diff import audit_candidate_semantic_diff
from src.impact_planning import (
    ActionKind, CallSiteDecision, CallSiteDisposition, ImpactPlan, PlannedAction,
)
from src.semantic_dependency_index import FORMAT, SCHEMA_VERSION, publish_declaration
from src.semantic_graph import ContentStore, Snapshot, make_snapshot


def declaration(kind, declaration_id, content=None, call_sites=None, references=None):
    return {
        "format": FORMAT,
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "declaration_id": declaration_id,
        "content": content or {},
        "references": references or [],
        "call_sites": call_sites or [],
    }


def site(target_hash):
    return [{
        "call_site_id": "call:tax",
        "targets": [{
            "target_id": "direct",
            "target_hash": target_hash,
            "condition": None,
        }],
    }]


def action(value_hash):
    return PlannedAction(ActionKind.REBUILD, value_hash, "covered by approved CIP")


def rewrite_action(value_hash):
    return PlannedAction(ActionKind.REWRITE_CALL_SITE, value_hash, "rewrite exact planned call site")


class CandidateSemanticDiffTests(unittest.TestCase):
    def setUp(self):
        self.store = ContentStore()
        self.old_callee = publish_declaration(
            self.store, declaration("function", "tax:v1", {"rule": "old"})
        )
        self.new_callee = publish_declaration(
            self.store, declaration("function", "tax:v2", {"rule": "new"})
        )
        self.old_caller = publish_declaration(
            self.store, declaration("function", "invoice:v1", {"body": "old"},
                                    call_sites=site(self.old_callee))
        )
        self.new_caller = publish_declaration(
            self.store, declaration("function", "invoice:v2", {"body": "new"},
                                    call_sites=site(self.new_callee))
        )

    def plan(self, baseline, candidate, actions=(), decisions=()):
        actions = tuple(actions)
        decisions = tuple(sorted(decisions))
        payload = {
            "baseline": baseline.root_hash,
            "candidate": candidate.root_hash,
            "policy": "policy:test",
            "actions": [
                (a.kind.value, a.artifact_hash, a.reason, a.prerequisite_hashes)
                for a in actions
            ],
            "audits": [],
            "audit_bindings": [],
            "call_site_decisions": [
                (d.caller_hash, d.call_site_id, d.target_id, d.base_callee_hash,
                 d.disposition.value, d.selected_callee_hash, d.resulting_caller_hash,
                 d.rationale, d.decision_evidence_id)
                for d in decisions
            ],
        }
        plan_id = hashlib.sha256(json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        return ImpactPlan(
            plan_id, baseline.root_hash, candidate.root_hash, "policy:test",
            actions, (), (), decisions,
        )

    def test_changed_selection_requires_exact_hash_action_coverage(self):
        revised = publish_declaration(
            self.store, declaration("function", "invoice:v1.1", {"body": "revised"},
                                    call_sites=site(self.old_callee))
        )
        baseline = make_snapshot({"invoice": self.old_caller, "tax": self.old_callee})
        candidate = make_snapshot({"invoice": revised, "tax": self.old_callee})
        result = audit_candidate_semantic_diff(
            self.store, baseline, candidate,
            self.plan(baseline, candidate, actions=(action(self.old_caller),)),
        )
        self.assertTrue(result.valid, result.errors)
        self.assertEqual([(row.logical_key, row.change_kind) for row in result.changes],
                         [("invoice", "changed")])

    def test_unplanned_selection_change_is_rejected(self):
        baseline = make_snapshot({"invoice": self.old_caller})
        candidate = make_snapshot({"invoice": self.new_caller})
        result = audit_candidate_semantic_diff(
            self.store, baseline, candidate, self.plan(baseline, candidate)
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("not covered by any CIP action" in error
                            for error in result.errors))

    def test_added_and_removed_selections_are_reported(self):
        baseline = make_snapshot({"old": self.old_callee})
        candidate = make_snapshot({"new": self.new_callee})
        result = audit_candidate_semantic_diff(
            self.store, baseline, candidate,
            self.plan(baseline, candidate,
                      actions=(action(self.old_callee), action(self.new_callee))),
        )
        self.assertTrue(result.valid, result.errors)
        self.assertEqual(
            {(row.logical_key, row.change_kind) for row in result.changes},
            {("old", "removed"), ("new", "added")},
        )

    def test_changed_call_target_requires_exact_matching_decision(self):
        baseline = make_snapshot({"tax": self.old_callee, "invoice": self.old_caller})
        candidate = make_snapshot({"tax": self.new_callee, "invoice": self.new_caller})
        decision = CallSiteDecision(
            self.old_caller, "call:tax", "direct", self.old_callee,
            CallSiteDisposition.MIGRATE, self.new_callee, self.new_caller,
            "new tax contract", "evidence:compatibility",
        )
        plan = self.plan(
            baseline, candidate,
            actions=(action(self.old_callee), rewrite_action(self.old_caller)),
            decisions=(decision,),
        )
        result = audit_candidate_semantic_diff(self.store, baseline, candidate, plan)
        self.assertTrue(result.valid, result.errors)

    def test_changed_callee_requires_decisions_for_unchanged_incoming_callers(self):
        baseline = make_snapshot({"tax": self.old_callee, "invoice": self.old_caller})
        candidate = make_snapshot({
            "tax": self.new_callee,
            "legacy-tax": self.old_callee,
            "invoice": self.old_caller,
        })
        decision = CallSiteDecision(
            self.old_caller, "call:tax", "direct", self.old_callee,
            CallSiteDisposition.PRESERVE, self.old_callee, self.old_caller,
            "retain legacy caller behavior", "evidence:preservation",
        )
        result = audit_candidate_semantic_diff(
            self.store, baseline, candidate,
            self.plan(baseline, candidate,
                      actions=(action(self.old_callee), action(self.new_callee)),
                      decisions=(decision,)),
        )
        self.assertTrue(result.valid, result.errors)

    def test_changed_callee_with_omitted_incoming_decision_is_rejected(self):
        baseline = make_snapshot({"tax": self.old_callee, "invoice": self.old_caller})
        candidate = make_snapshot({
            "tax": self.new_callee,
            "legacy-tax": self.old_callee,
            "invoice": self.old_caller,
        })
        result = audit_candidate_semantic_diff(
            self.store, baseline, candidate,
            self.plan(baseline, candidate,
                      actions=(action(self.old_callee), action(self.new_callee))),
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("independently scanned Snapshot" in error
                            for error in result.errors))

    def test_changed_call_target_without_decision_is_rejected(self):
        baseline = make_snapshot({"tax": self.old_callee, "invoice": self.old_caller})
        candidate = make_snapshot({"tax": self.new_callee, "invoice": self.new_caller})
        result = audit_candidate_semantic_diff(
            self.store, baseline, candidate,
            self.plan(baseline, candidate,
                      actions=(action(self.old_callee), rewrite_action(self.old_caller))),
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("no exact CIP decision" in error for error in result.errors))

    def test_decision_cannot_claim_a_different_candidate_target(self):
        baseline = make_snapshot({"tax": self.old_callee, "invoice": self.old_caller})
        candidate = make_snapshot({"tax": self.new_callee, "invoice": self.new_caller})
        decision = CallSiteDecision(
            self.old_caller, "call:tax", "direct", self.old_callee,
            CallSiteDisposition.MIGRATE, self.old_callee, self.new_caller,
            "wrong target", "evidence:compatibility",
        )
        result = audit_candidate_semantic_diff(
            self.store, baseline, candidate,
            self.plan(baseline, candidate,
                      actions=(action(self.old_callee), rewrite_action(self.old_caller)),
                      decisions=(decision,)),
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("CIP selected callee differs from candidate target" in error
                            for error in result.errors))

    def test_malformed_snapshot_fails_closed_without_raising(self):
        baseline = Snapshot("forged", ((["not", "a", "logical-key"], self.old_caller),))
        candidate = make_snapshot({"invoice": self.old_caller})
        result = audit_candidate_semantic_diff(
            self.store, baseline, candidate,
            self.plan(baseline, candidate, actions=(action(self.old_caller),)),
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("non-string" in error or "materialization check failed" in error
                            for error in result.errors))

    def test_typed_reference_change_is_rejected(self):
        contract = publish_declaration(
            self.store, declaration("contract", "contract:invoice")
        )
        old = publish_declaration(
            self.store, declaration(
                "function", "invoice:ref-old", {"body": "same"},
                call_sites=site(self.old_callee),
            )
        )
        new = publish_declaration(
            self.store, declaration(
                "function", "invoice:ref-new", {"body": "same"},
                references=[{
                    "reference_id": "contract",
                    "relation": "uses_contract",
                    "target_hash": contract,
                    "target_kind": "contract",
                    "condition": None,
                }],
                call_sites=site(self.old_callee),
            )
        )
        baseline = make_snapshot({"invoice": old, "tax": self.old_callee})
        candidate = make_snapshot({"invoice": new, "tax": self.old_callee})
        result = audit_candidate_semantic_diff(
            self.store, baseline, candidate,
            self.plan(baseline, candidate, actions=(action(old),)),
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("typed-reference change" in error for error in result.errors))
        self.assertEqual(len(result.edge_changes), 1)

    def test_forged_plan_identity_is_rejected(self):
        from dataclasses import replace

        baseline = make_snapshot({"invoice": self.old_caller})
        candidate = make_snapshot({"invoice": self.new_caller})
        plan = self.plan(baseline, candidate, actions=(action(self.old_caller),))
        forged = replace(plan, plan_id="forged")
        result = audit_candidate_semantic_diff(self.store, baseline, candidate, forged)
        self.assertFalse(result.valid)
        self.assertTrue(any("plan_id does not match" in error for error in result.errors))

    def test_diff_digest_is_deterministic_and_bound_to_plan(self):
        baseline = make_snapshot({"invoice": self.old_caller})
        candidate = make_snapshot({"invoice": self.new_caller})
        plan = self.plan(baseline, candidate,
                         actions=(action(self.old_caller),))
        first = audit_candidate_semantic_diff(self.store, baseline, candidate, plan)
        second = audit_candidate_semantic_diff(self.store, baseline, candidate, plan)
        self.assertEqual(first.diff_digest, second.diff_digest)
        self.assertTrue(first.baseline_graph_digest)
        self.assertTrue(first.candidate_graph_digest)
        self.assertTrue(first.baseline_edge_set_digest)
        self.assertTrue(first.candidate_edge_set_digest)
        self.assertEqual(first.plan_id, plan.plan_id)
        self.assertEqual(first.baseline_root, baseline.root_hash)
        self.assertEqual(first.candidate_root, candidate.root_hash)


if __name__ == "__main__":
    unittest.main()
