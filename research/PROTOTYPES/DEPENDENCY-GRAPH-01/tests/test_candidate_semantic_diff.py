import hashlib
import json
import unittest

from src.candidate_semantic_diff import audit_candidate_semantic_diff
from src.impact_planning import (
    ActionKind, CallSiteDecision, CallSiteDisposition, ImpactPlan, PlannedAction,
    OutputOperation, PlannedOutput, PlannedEdgeKind, PlannedEdgeOperation,
    PlannedEdgeChange, compute_impact_plan_id,
)
from src.semantic_dependency_index import (
    FORMAT, SCHEMA_VERSION, publish_declaration, validate_declaration,
)
from src.semantic_graph import ContentStore, Snapshot, canonical_bytes, make_snapshot


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


def planned_output(store, output_id, logical_key, operation, base_hash, candidate_hash,
                   rationale="approved semantic output", evidence_id="evidence:output",
                   source_hash=None, consumer_path_id=""):
    if operation is OutputOperation.REMOVE:
        kind = content_digest = None
    else:
        value = store.get(candidate_hash)
        declaration_value = validate_declaration(value.payload)
        kind = declaration_value["kind"]
        content_digest = hashlib.sha256(
            canonical_bytes(declaration_value["content"])
        ).hexdigest()
    return PlannedOutput(
        output_id, logical_key, operation, base_hash, kind, content_digest,
        rationale, evidence_id, source_hash, consumer_path_id,
    )


def planned_edge(output_id, edge_kind, edge_id, operation, relation,
                 old_target=None, new_target=None, old_condition=None,
                 new_condition=None):
    return PlannedEdgeChange(
        output_id, edge_kind, edge_id, operation,
        relation if old_target is not None else None,
        relation if new_target is not None else None,
        old_target, new_target, old_condition, new_condition,
        "approved exact edge delta", "evidence:edge",
    )


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

    def plan(self, baseline, candidate, actions=(), decisions=(),
             outputs=(), edge_changes=()):
        provisional = ImpactPlan(
            "", baseline.root_hash, candidate.root_hash, "policy:test",
            tuple(actions), (), (), tuple(sorted(decisions)),
            tuple(sorted(outputs)), tuple(sorted(edge_changes)),
        )
        return ImpactPlan(
            compute_impact_plan_id(provisional), provisional.baseline_root,
            provisional.candidate_root, provisional.policy_id,
            provisional.actions, provisional.audit_statuses,
            provisional.audit_bindings, provisional.call_site_decisions,
            provisional.planned_outputs, provisional.planned_edge_changes,
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
            self.plan(baseline, candidate, actions=(action(self.old_caller),),
                      outputs=(planned_output(self.store, "invoice-v1.1", "invoice",
                          OutputOperation.REPLACE, self.old_caller, revised),)),
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
                      actions=(action(self.old_callee), action(self.new_callee)),
                      outputs=(
                          planned_output(self.store, "old-tax", "old", OutputOperation.REMOVE,
                                         self.old_callee, None),
                          planned_output(self.store, "new-tax", "new", OutputOperation.ADD,
                                         None, self.new_callee),
                      )),
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
            "new tax contract", "evidence:compatibility", "", "invoice-output",
        )
        plan = self.plan(
            baseline, candidate,
            actions=(action(self.old_callee), rewrite_action(self.old_caller)),
            decisions=(decision,),
            outputs=(
                planned_output(self.store, "tax-output", "tax", OutputOperation.REPLACE,
                               self.old_callee, self.new_callee),
                planned_output(self.store, "invoice-output", "invoice", OutputOperation.REPLACE,
                               self.old_caller, self.new_caller),
            ),
            edge_changes=(planned_edge(
                "invoice-output", PlannedEdgeKind.CALL_TARGET, "call:tax/direct",
                PlannedEdgeOperation.REWRITE, "calls", self.old_callee,
                self.new_callee,
            ),),
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
                      decisions=(decision,),
                      outputs=(
                          planned_output(self.store, "tax-output", "tax", OutputOperation.REPLACE,
                                         self.old_callee, self.new_callee),
                          planned_output(self.store, "legacy-output", "legacy-tax", OutputOperation.ADD,
                                         None, self.old_callee),
                      )),
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
                      actions=(action(self.old_callee), action(self.new_callee)),
                      outputs=(
                          planned_output(self.store, "tax-output", "tax", OutputOperation.REPLACE,
                                         self.old_callee, self.new_callee),
                          planned_output(self.store, "legacy-output", "legacy-tax", OutputOperation.ADD,
                                         None, self.old_callee),
                      )),
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
                      actions=(action(self.old_callee), rewrite_action(self.old_caller)),
                      outputs=(
                          planned_output(self.store, "tax-output", "tax", OutputOperation.REPLACE,
                                         self.old_callee, self.new_callee),
                          planned_output(self.store, "invoice-output", "invoice", OutputOperation.REPLACE,
                                         self.old_caller, self.new_caller),
                      ),
                      edge_changes=(planned_edge(
                          "invoice-output", PlannedEdgeKind.CALL_TARGET, "call:tax/direct",
                          PlannedEdgeOperation.REWRITE, "calls", self.old_callee,
                          self.new_callee,
                      ),)),
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("no exact CIP decision" in error for error in result.errors))

    def test_decision_cannot_claim_a_different_candidate_target(self):
        baseline = make_snapshot({"tax": self.old_callee, "invoice": self.old_caller})
        candidate = make_snapshot({"tax": self.new_callee, "invoice": self.new_caller})
        decision = CallSiteDecision(
            self.old_caller, "call:tax", "direct", self.old_callee,
            CallSiteDisposition.MIGRATE, self.old_callee, self.new_caller,
            "wrong target", "evidence:compatibility", "", "invoice-output",
        )
        result = audit_candidate_semantic_diff(
            self.store, baseline, candidate,
            self.plan(baseline, candidate,
                      actions=(action(self.old_callee), rewrite_action(self.old_caller)),
                      decisions=(decision,),
                      outputs=(
                          planned_output(self.store, "tax-output", "tax", OutputOperation.REPLACE,
                                         self.old_callee, self.new_callee),
                          planned_output(self.store, "invoice-output", "invoice", OutputOperation.REPLACE,
                                         self.old_caller, self.new_caller),
                      ),
                      edge_changes=(planned_edge(
                          "invoice-output", PlannedEdgeKind.CALL_TARGET, "call:tax/direct",
                          PlannedEdgeOperation.REWRITE, "calls", self.old_callee,
                          self.new_callee,
                      ),)),
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

    def test_typed_reference_change_requires_and_accepts_exact_cip_record(self):
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
        baseline = make_snapshot({"invoice": old, "tax": self.old_callee, "contract": contract})
        candidate = make_snapshot({"invoice": new, "tax": self.old_callee, "contract": contract})
        result = audit_candidate_semantic_diff(
            self.store, baseline, candidate,
            self.plan(baseline, candidate, actions=(action(old),),
                      outputs=(planned_output(self.store, "invoice-ref", "invoice",
                          OutputOperation.REPLACE, old, new),),
                      edge_changes=(planned_edge(
                          "invoice-ref", PlannedEdgeKind.TYPED_REFERENCE, "contract",
                          PlannedEdgeOperation.ADD, "uses_contract", None, contract,
                      ),)),
        )
        self.assertTrue(result.valid, result.errors)
        self.assertEqual(len(result.edge_changes), 1)
        self.assertEqual(result.materialized_outputs[0].candidate_hash, new)

    def test_forged_plan_identity_is_rejected(self):
        from dataclasses import replace

        baseline = make_snapshot({"invoice": self.old_caller})
        candidate = make_snapshot({"invoice": self.new_caller})
        plan = self.plan(baseline, candidate, actions=(action(self.old_caller),),
                         outputs=(planned_output(self.store, "invoice-output", "invoice",
                             OutputOperation.REPLACE, self.old_caller, self.new_caller),))
        forged = replace(plan, plan_id="forged")
        result = audit_candidate_semantic_diff(self.store, baseline, candidate, forged)
        self.assertFalse(result.valid)
        self.assertTrue(any("plan_id does not match" in error for error in result.errors))

    def test_shared_caller_fork_is_bound_to_consumer_paths(self):
        old_leaf = publish_declaration(
            self.store, declaration("function", "leaf:v1", {"value": 1})
        )
        new_leaf = publish_declaration(
            self.store, declaration("function", "leaf:v2", {"value": 2})
        )
        old_shared = publish_declaration(
            self.store, declaration("function", "shared:v1", {"body": "shared"},
                call_sites=site(old_leaf))
        )
        new_shared = publish_declaration(
            self.store, declaration("function", "shared:v2", {"body": "shared"},
                call_sites=site(new_leaf))
        )
        old_consumer = publish_declaration(
            self.store, declaration("function", "consumer:legacy", {"body": "legacy"},
                call_sites=[{
                    "call_site_id": "call:shared",
                    "targets": [{"target_id": "direct", "target_hash": old_shared, "condition": None}],
                }])
        )
        old_modern_consumer = publish_declaration(
            self.store, declaration("function", "consumer:modern:v1", {"body": "modern"},
                call_sites=[{
                    "call_site_id": "call:shared",
                    "targets": [{"target_id": "direct", "target_hash": old_shared, "condition": None}],
                }])
        )
        new_modern_consumer = publish_declaration(
            self.store, declaration("function", "consumer:modern:v2", {"body": "modern"},
                call_sites=[{
                    "call_site_id": "call:shared",
                    "targets": [{"target_id": "direct", "target_hash": new_shared, "condition": None}],
                }])
        )
        baseline = make_snapshot({
            "leaf": old_leaf,
            "shared": old_shared,
            "legacy-consumer": old_consumer,
            "modern-consumer": old_modern_consumer,
        })
        candidate = make_snapshot({
            "leaf": new_leaf,
            "leaf-legacy": old_leaf,
            "shared-legacy": old_shared,
            "shared-modern": new_shared,
            "legacy-consumer": old_consumer,
            "modern-consumer": new_modern_consumer,
        })
        outputs = (
            planned_output(self.store, "leaf-v2", "leaf", OutputOperation.REPLACE,
                           old_leaf, new_leaf),
            planned_output(self.store, "leaf-v1-alias", "leaf-legacy", OutputOperation.ADD,
                           None, old_leaf, source_hash=old_leaf),
            planned_output(self.store, "shared-remove", "shared", OutputOperation.REMOVE,
                           old_shared, None),
            planned_output(self.store, "shared-legacy", "shared-legacy", OutputOperation.ADD,
                           None, old_shared, source_hash=old_shared,
                           consumer_path_id="legacy-consumer"),
            planned_output(self.store, "shared-modern", "shared-modern", OutputOperation.ADD,
                           None, new_shared, source_hash=old_shared,
                           consumer_path_id="modern-consumer"),
            planned_output(self.store, "modern-consumer-v2", "modern-consumer",
                           OutputOperation.REPLACE, old_modern_consumer, new_modern_consumer,
                           consumer_path_id="modern-consumer"),
        )
        decisions = (
            CallSiteDecision(
                old_shared, "call:tax", "direct", old_leaf,
                CallSiteDisposition.PRESERVE, old_leaf, old_shared,
                "legacy consumer retains the original shared caller", "evidence:legacy",
                "legacy-consumer", "shared-legacy",
            ),
            CallSiteDecision(
                old_shared, "call:tax", "direct", old_leaf,
                CallSiteDisposition.MIGRATE, new_leaf, new_shared,
                "modern consumer receives a forked shared caller", "evidence:modern",
                "modern-consumer", "shared-modern",
            ),
            CallSiteDecision(
                old_consumer, "call:shared", "direct", old_shared,
                CallSiteDisposition.PRESERVE, old_shared, old_consumer,
                "legacy consumer remains on the old shared caller", "evidence:legacy-consumer",
            ),
            CallSiteDecision(
                old_modern_consumer, "call:shared", "direct", old_shared,
                CallSiteDisposition.MIGRATE, new_shared, new_modern_consumer,
                "modern consumer migrates to its caller fork", "evidence:modern-consumer",
                "modern-consumer", "modern-consumer-v2",
            ),
        )
        edge_changes = (
            planned_edge(
                "shared-modern", PlannedEdgeKind.CALL_TARGET, "call:tax/direct",
                PlannedEdgeOperation.REWRITE, "calls", old_leaf, new_leaf,
            ),
            planned_edge(
                "modern-consumer-v2", PlannedEdgeKind.CALL_TARGET, "call:shared/direct",
                PlannedEdgeOperation.REWRITE, "calls", old_shared, new_shared,
            ),
        )
        plan = self.plan(
            baseline, candidate,
            actions=(
                action(old_leaf), action(new_leaf), action(old_shared), action(new_shared),
                rewrite_action(old_shared), rewrite_action(old_modern_consumer),
            ),
            decisions=decisions, outputs=outputs, edge_changes=edge_changes,
        )
        result = audit_candidate_semantic_diff(self.store, baseline, candidate, plan)
        self.assertTrue(result.valid, result.errors)
        self.assertEqual(
            {item.output_id for item in result.materialized_outputs},
            {item.output_id for item in outputs},
        )
        self.assertEqual(
            {item.candidate_hash for item in result.materialized_outputs
             if item.output_id in {"shared-legacy", "shared-modern"}},
            {old_shared, new_shared},
        )

    def test_diff_digest_is_deterministic_and_bound_to_plan(self):
        baseline = make_snapshot({"invoice": self.old_caller, "tax": self.old_callee})
        candidate = make_snapshot({"invoice": self.new_caller, "tax": self.new_callee})
        decision = CallSiteDecision(
            self.old_caller, "call:tax", "direct", self.old_callee,
            CallSiteDisposition.MIGRATE, self.new_callee, self.new_caller,
            "new tax contract", "evidence:compatibility", "", "invoice-output",
        )
        plan = self.plan(
            baseline, candidate,
            actions=(action(self.old_callee), rewrite_action(self.old_caller)),
            decisions=(decision,),
            outputs=(
                planned_output(self.store, "tax-output", "tax", OutputOperation.REPLACE,
                               self.old_callee, self.new_callee),
                planned_output(self.store, "invoice-output", "invoice", OutputOperation.REPLACE,
                               self.old_caller, self.new_caller),
            ),
            edge_changes=(planned_edge(
                "invoice-output", PlannedEdgeKind.CALL_TARGET, "call:tax/direct",
                PlannedEdgeOperation.REWRITE, "calls", self.old_callee,
                self.new_callee,
            ),),
        )
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
