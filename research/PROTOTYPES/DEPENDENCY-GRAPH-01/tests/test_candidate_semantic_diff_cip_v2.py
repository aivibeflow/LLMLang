import hashlib
import unittest

from src.candidate_semantic_diff import (
    audit_candidate_semantic_diff, _declaration_edges, _edge_record_matches,
)
from src.impact_planning import (
    ActionKind, CallSiteDecision, CallSiteDisposition, ImpactPlan, PlannedAction,
    OutputOperation, PlannedOutput, PlannedEdgeKind, PlannedEdgeOperation,
    PlannedEdgeChange, assign_planned_action_ids, compute_impact_plan_id,
)
from src.semantic_dependency_index import FORMAT, SCHEMA_VERSION, publish_declaration
from src.semantic_graph import ContentStore, canonical_bytes, make_snapshot


def declaration(kind, declaration_id, content=None, references=(), call_sites=()):
    return {
        "format": FORMAT,
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "declaration_id": declaration_id,
        "content": content or {},
        "references": list(references),
        "call_sites": list(call_sites),
    }


def call_site(site_id, target_hash, required_contract_hash, condition=None, target_id="direct"):
    return {
        "call_site_id": site_id,
        "targets": [{
            "target_id": target_id,
            "target_hash": target_hash,
            "condition": condition,
            "required_contract_hash": required_contract_hash,
        }],
    }


def action(value_hash):
    return PlannedAction(ActionKind.REBUILD, value_hash, "approved by CIP output record")


def rewrite_action(value_hash):
    return PlannedAction(ActionKind.REWRITE_CALL_SITE, value_hash, "rewrite exact planned call site")


def output_record(store, output_id, logical_key, operation, base_hash, candidate_hash,
                  source_hash=None, consumer_path_id="", rationale="approved output"):
    if operation is OutputOperation.REMOVE:
        kind = payload_digest = None
    else:
        value = store.get(candidate_hash)
        payload = value.payload
        kind = payload["kind"]
        payload_digest = hashlib.sha256(canonical_bytes({
            "declaration_id": payload["declaration_id"],
            "content": payload["content"],
        })).hexdigest()
    return PlannedOutput(
        output_id, logical_key, operation, base_hash, kind, payload_digest,
        rationale, "evidence:output:" + output_id, source_hash, consumer_path_id,
    )


def edge_record(output_id, edge_kind, edge_id, operation, old_relation, new_relation,
                old_target, new_target, old_condition=None, new_condition=None,
                old_required=None, new_required=None):
    return PlannedEdgeChange(
        output_id, edge_kind, edge_id, operation,
        old_relation, new_relation, old_target, new_target,
        old_condition, new_condition,
        "approved exact semantic edge delta", "evidence:edge:" + output_id + ":" + edge_id,
        old_required, new_required,
    )


def decision(caller_hash, site_id, target_id, base_callee_hash, disposition,
             selected_callee_hash, resulting_caller_hash, required_contract_hash,
             base_contract_hash, selected_contract_hash, consumer_path_id="",
             resulting_output_id=None, selected_output_id=None,
             candidate_required_contract_hash=None):
    return CallSiteDecision(
        caller_hash, site_id, target_id, base_callee_hash, disposition,
        selected_callee_hash, resulting_caller_hash,
        "contract-bound decision with explicit evidence",
        "evidence:compatibility:" + (consumer_path_id or "default"),
        required_contract_hash, base_contract_hash, selected_contract_hash, "PROVEN",
        candidate_required_contract_hash, consumer_path_id,
        resulting_output_id, selected_output_id,
    )


class CandidateSemanticDiffCIPV2Tests(unittest.TestCase):
    def setUp(self):
        self.store = ContentStore()
        self.contract = publish_declaration(
            self.store, declaration("contract", "contract:shared", {"name": "SharedContract"})
        )

    def publish_function(self, declaration_id, content, calls=(), references=()):
        provided = {
            "reference_id": "provided-contract",
            "relation": "provides_contract",
            "target_hash": self.contract,
            "target_kind": "contract",
            "condition": None,
        }
        return publish_declaration(
            self.store,
            declaration("function", declaration_id, content,
                        references=(provided, *references), call_sites=calls),
        )

    def make_plan(self, baseline, candidate, actions=(), decisions=(),
                  outputs=(), edge_changes=()):
        identified_actions = assign_planned_action_ids(tuple(actions))
        provisional = ImpactPlan(
            "", baseline.root_hash, candidate.root_hash, "policy:cip-v2",
            identified_actions, (), (), tuple(sorted(decisions)),
            tuple(sorted(outputs)), tuple(sorted(edge_changes)),
        )
        return ImpactPlan(
            compute_impact_plan_id(provisional), provisional.baseline_root,
            provisional.candidate_root, provisional.policy_id,
            provisional.actions, provisional.audit_statuses,
            provisional.audit_bindings, provisional.call_site_decisions,
            provisional.planned_outputs, provisional.planned_edge_changes,
        )

    def audit(self, baseline, candidate, actions=(), decisions=(),
              outputs=(), edge_changes=()):
        return audit_candidate_semantic_diff(
            self.store, baseline, candidate,
            self.make_plan(baseline, candidate, actions, decisions, outputs, edge_changes),
        )

    def test_unknown_caller_and_callee_hashes_resolve_through_output_ids(self):
        old_callee = self.publish_function("tax:v1", {"rate": 10})
        new_callee = self.publish_function("tax:v2", {"rate": 12})
        old_caller = self.publish_function(
            "invoice:v1", {"body": "invoice"},
            calls=(call_site("call:tax", old_callee, self.contract),),
        )
        new_caller = self.publish_function(
            "invoice:v2", {"body": "invoice"},
            calls=(call_site("call:tax", new_callee, self.contract),),
        )
        baseline = make_snapshot({
            "contract": self.contract, "tax": old_callee, "invoice": old_caller,
        })
        candidate = make_snapshot({
            "contract": self.contract, "tax": new_callee, "invoice": new_caller,
        })
        outputs = (
            output_record(self.store, "tax-v2", "tax", OutputOperation.REPLACE,
                          old_callee, new_callee),
            output_record(self.store, "invoice-v2", "invoice", OutputOperation.REPLACE,
                          old_caller, new_caller),
        )
        decisions = (decision(
            old_caller, "call:tax", "direct", old_callee,
            CallSiteDisposition.MIGRATE, None, None, self.contract, self.contract,
            self.contract, resulting_output_id="invoice-v2", selected_output_id="tax-v2",
        ),)
        edges = (edge_record(
            "invoice-v2", PlannedEdgeKind.CALL_TARGET, "call:tax/direct",
            PlannedEdgeOperation.REWRITE, "calls", "calls", old_callee, new_callee,
            old_required=self.contract, new_required=self.contract,
        ),)
        result = self.audit(
            baseline, candidate,
            actions=(action(old_callee), rewrite_action(old_caller)),
            decisions=decisions, outputs=outputs, edge_changes=edges,
        )
        self.assertTrue(result.valid, result.errors)
        bindings = {row.output_id: row.candidate_hash for row in result.materialized_outputs}
        self.assertEqual(bindings, {"tax-v2": new_callee, "invoice-v2": new_caller})

    def test_typed_reference_addition_is_reconciled_exactly(self):
        extra_contract = publish_declaration(
            self.store, declaration("contract", "contract:extra", {"name": "Extra"})
        )
        old = self.publish_function("invoice:old", {"body": "same"})
        new = self.publish_function(
            "invoice:new", {"body": "same"},
            references=({
                "reference_id": "extra",
                "relation": "uses_contract",
                "target_hash": extra_contract,
                "target_kind": "contract",
                "condition": None,
            },),
        )
        baseline = make_snapshot({
            "contract": self.contract, "extra-contract": extra_contract, "invoice": old,
        })
        candidate = make_snapshot({
            "contract": self.contract, "extra-contract": extra_contract, "invoice": new,
        })
        result = self.audit(
            baseline, candidate, actions=(action(old),),
            outputs=(output_record(self.store, "invoice-v2", "invoice",
                                   OutputOperation.REPLACE, old, new),),
            edge_changes=(edge_record(
                "invoice-v2", PlannedEdgeKind.TYPED_REFERENCE, "extra",
                PlannedEdgeOperation.ADD, None, "uses_contract", None, extra_contract,
            ),),
        )
        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.edge_changes[0].candidate_target_hash, extra_contract)

    def test_call_target_addition_is_reconciled(self):
        callee = self.publish_function("tax:v1", {"rate": 10})
        old = self.publish_function("invoice:no-call", {"body": "invoice"})
        new = self.publish_function(
            "invoice:with-call", {"body": "invoice"},
            calls=(call_site("call:tax", callee, self.contract),),
        )
        baseline = make_snapshot({"contract": self.contract, "tax": callee, "invoice": old})
        candidate = make_snapshot({"contract": self.contract, "tax": callee, "invoice": new})
        result = self.audit(
            baseline, candidate, actions=(action(old),),
            outputs=(output_record(self.store, "invoice-v2", "invoice",
                                   OutputOperation.REPLACE, old, new),),
            edge_changes=(edge_record(
                "invoice-v2", PlannedEdgeKind.CALL_TARGET, "call:tax/direct",
                PlannedEdgeOperation.ADD, None, "calls", None, callee,
                new_required=self.contract,
            ),),
        )
        self.assertTrue(result.valid, result.errors)

    def test_call_target_removal_is_reconciled(self):
        callee = self.publish_function("tax:v1", {"rate": 10})
        old = self.publish_function(
            "invoice:with-call", {"body": "invoice"},
            calls=(call_site("call:tax", callee, self.contract),),
        )
        new = self.publish_function("invoice:no-call", {"body": "invoice"})
        baseline = make_snapshot({"contract": self.contract, "tax": callee, "invoice": old})
        candidate = make_snapshot({"contract": self.contract, "tax": callee, "invoice": new})
        result = self.audit(
            baseline, candidate, actions=(action(old),),
            outputs=(output_record(self.store, "invoice-v2", "invoice",
                                   OutputOperation.REPLACE, old, new),),
            edge_changes=(edge_record(
                "invoice-v2", PlannedEdgeKind.CALL_TARGET, "call:tax/direct",
                PlannedEdgeOperation.REMOVE, "calls", None, callee, None,
                old_required=self.contract,
            ),),
        )
        self.assertTrue(result.valid, result.errors)

    def test_call_condition_change_is_reconciled(self):
        callee = self.publish_function("tax:v1", {"rate": 10})
        old = self.publish_function(
            "invoice:condition-old", {"body": "invoice"},
            calls=(call_site("call:tax", callee, self.contract, "mode == legacy"),),
        )
        new = self.publish_function(
            "invoice:condition-new", {"body": "invoice"},
            calls=(call_site("call:tax", callee, self.contract, "mode == modern"),),
        )
        baseline = make_snapshot({"contract": self.contract, "tax": callee, "invoice": old})
        candidate = make_snapshot({"contract": self.contract, "tax": callee, "invoice": new})
        result = self.audit(
            baseline, candidate, actions=(action(old),),
            outputs=(output_record(self.store, "invoice-v2", "invoice",
                                   OutputOperation.REPLACE, old, new),),
            edge_changes=(edge_record(
                "invoice-v2", PlannedEdgeKind.CALL_TARGET, "call:tax/direct",
                PlannedEdgeOperation.CONDITION, "calls", "calls", callee, callee,
                "mode == legacy", "mode == modern", self.contract, self.contract,
            ),),
        )
        self.assertTrue(result.valid, result.errors)

    def test_deleted_caller_needs_edge_removal_not_migration_decision(self):
        old_callee = self.publish_function("tax:v1", {"rate": 10})
        new_callee = self.publish_function("tax:v2", {"rate": 12})
        old_caller = self.publish_function(
            "invoice:removed", {"body": "obsolete"},
            calls=(call_site("call:tax", old_callee, self.contract),),
        )
        baseline = make_snapshot({
            "contract": self.contract, "tax": old_callee, "invoice": old_caller,
        })
        candidate = make_snapshot({
            "contract": self.contract, "tax": new_callee,
        })
        outputs = (
            output_record(self.store, "tax-v2", "tax", OutputOperation.REPLACE,
                          old_callee, new_callee),
            output_record(self.store, "invoice-remove", "invoice", OutputOperation.REMOVE,
                          old_caller, None),
        )
        edges = (
            edge_record(
                "invoice-remove", PlannedEdgeKind.TYPED_REFERENCE, "provided-contract",
                PlannedEdgeOperation.REMOVE, "provides_contract", None, self.contract, None,
            ),
            edge_record(
                "invoice-remove", PlannedEdgeKind.CALL_TARGET, "call:tax/direct",
                PlannedEdgeOperation.REMOVE, "calls", None, old_callee, None,
                old_required=self.contract,
            ),
        )
        result = self.audit(
            baseline, candidate,
            actions=(action(old_callee), action(new_callee), action(old_caller)),
            outputs=outputs, edge_changes=edges,
        )
        self.assertTrue(result.valid, result.errors)

    def test_shared_caller_fork_is_bound_to_consumer_paths(self):
        old_leaf = self.publish_function("leaf:v1", {"value": 1})
        new_leaf = self.publish_function("leaf:v2", {"value": 2})
        old_shared = self.publish_function(
            "shared:v1", {"body": "shared"},
            calls=(call_site("call:leaf", old_leaf, self.contract),),
        )
        new_shared = self.publish_function(
            "shared:v2", {"body": "shared"},
            calls=(call_site("call:leaf", new_leaf, self.contract),),
        )
        old_legacy_consumer = self.publish_function(
            "consumer:legacy", {"body": "legacy"},
            calls=(call_site("call:shared", old_shared, self.contract),),
        )
        old_modern_consumer = self.publish_function(
            "consumer:modern:v1", {"body": "modern"},
            calls=(call_site("call:shared", old_shared, self.contract),),
        )
        new_modern_consumer = self.publish_function(
            "consumer:modern:v2", {"body": "modern"},
            calls=(call_site("call:shared", new_shared, self.contract),),
        )
        baseline = make_snapshot({
            "contract": self.contract, "leaf": old_leaf, "shared": old_shared,
            "legacy-consumer": old_legacy_consumer,
            "modern-consumer": old_modern_consumer,
        })
        candidate = make_snapshot({
            "contract": self.contract, "leaf": new_leaf, "leaf-legacy": old_leaf,
            "shared-legacy": old_shared, "shared-modern": new_shared,
            "legacy-consumer": old_legacy_consumer,
            "modern-consumer": new_modern_consumer,
        })
        outputs = (
            output_record(self.store, "leaf-v2", "leaf", OutputOperation.REPLACE,
                          old_leaf, new_leaf),
            output_record(self.store, "leaf-v1-alias", "leaf-legacy", OutputOperation.ADD,
                          None, old_leaf),
            output_record(self.store, "shared-remove", "shared", OutputOperation.REMOVE,
                          old_shared, None),
            output_record(self.store, "shared-legacy", "shared-legacy", OutputOperation.ADD,
                          None, old_shared, old_shared, "legacy-consumer"),
            output_record(self.store, "shared-modern", "shared-modern", OutputOperation.ADD,
                          None, new_shared, old_shared, "modern-consumer"),
            output_record(self.store, "modern-consumer-v2", "modern-consumer",
                          OutputOperation.REPLACE, old_modern_consumer, new_modern_consumer,
                          consumer_path_id="modern-consumer"),
        )
        decisions = (
            decision(old_shared, "call:leaf", "direct", old_leaf,
                     CallSiteDisposition.PRESERVE, old_leaf, old_shared,
                     self.contract, self.contract, self.contract,
                     "legacy-consumer", "shared-legacy"),
            decision(old_shared, "call:leaf", "direct", old_leaf,
                     CallSiteDisposition.MIGRATE, None, None,
                     self.contract, self.contract, self.contract,
                     "modern-consumer", "shared-modern", "leaf-v2"),
            decision(old_legacy_consumer, "call:shared", "direct", old_shared,
                     CallSiteDisposition.PRESERVE, old_shared, old_legacy_consumer,
                     self.contract, self.contract, self.contract),
            decision(old_modern_consumer, "call:shared", "direct", old_shared,
                     CallSiteDisposition.MIGRATE, None, None,
                     self.contract, self.contract, self.contract,
                     "modern-consumer", "modern-consumer-v2", "shared-modern"),
        )
        edges = (
            edge_record("shared-modern", PlannedEdgeKind.CALL_TARGET, "call:leaf/direct",
                        PlannedEdgeOperation.REWRITE, "calls", "calls", old_leaf, new_leaf,
                        old_required=self.contract, new_required=self.contract),
            edge_record("modern-consumer-v2", PlannedEdgeKind.CALL_TARGET, "call:shared/direct",
                        PlannedEdgeOperation.REWRITE, "calls", "calls", old_shared, new_shared,
                        old_required=self.contract, new_required=self.contract),
        )
        result = self.audit(
            baseline, candidate,
            actions=(action(old_leaf), action(new_leaf), action(old_shared),
                     action(new_shared), rewrite_action(old_shared),
                     rewrite_action(old_modern_consumer)),
            decisions=decisions, outputs=outputs, edge_changes=edges,
        )
        self.assertTrue(result.valid, result.errors)
        bindings = {row.output_id: row.candidate_hash for row in result.materialized_outputs}
        self.assertEqual(bindings["shared-legacy"], old_shared)
        self.assertEqual(bindings["shared-modern"], new_shared)

    def test_required_contract_change_needs_exact_edge_and_compatibility_records(self):
        alternate = publish_declaration(
            self.store, declaration("contract", "contract:alternate", {"name": "Alternate"})
        )
        old_callee = self.publish_function("tax:old", {"rate": 10})
        new_callee = publish_declaration(
            self.store, declaration(
                "function", "tax:new", {"rate": 12},
                references=({
                    "reference_id": "provided-contract",
                    "relation": "provides_contract",
                    "target_hash": alternate,
                    "target_kind": "contract",
                    "condition": None,
                },),
            ),
        )
        old_caller = self.publish_function(
            "invoice:old", {"body": "invoice"},
            calls=(call_site("call:tax", old_callee, self.contract),),
        )
        new_caller = publish_declaration(
            self.store, declaration(
                "function", "invoice:new", {"body": "invoice"},
                references=({
                    "reference_id": "provided-contract",
                    "relation": "provides_contract",
                    "target_hash": self.contract,
                    "target_kind": "contract",
                    "condition": None,
                },),
                call_sites=(call_site("call:tax", new_callee, alternate),),
            ),
        )
        baseline = make_snapshot({
            "contract": self.contract, "alternate": alternate,
            "tax": old_callee, "invoice": old_caller,
        })
        candidate = make_snapshot({
            "contract": self.contract, "alternate": alternate,
            "tax": new_callee, "invoice": new_caller,
        })
        outputs = (
            output_record(self.store, "tax-v2", "tax", OutputOperation.REPLACE,
                          old_callee, new_callee),
            output_record(self.store, "invoice-v2", "invoice", OutputOperation.REPLACE,
                          old_caller, new_caller),
        )
        decisions = (decision(
            old_caller, "call:tax", "direct", old_callee,
            CallSiteDisposition.MIGRATE, None, None, self.contract, self.contract,
            alternate, resulting_output_id="invoice-v2", selected_output_id="tax-v2",
            candidate_required_contract_hash=alternate,
        ),)
        edges = (
            edge_record(
                "tax-v2", PlannedEdgeKind.TYPED_REFERENCE, "provided-contract",
                PlannedEdgeOperation.REWRITE, "provides_contract", "provides_contract",
                self.contract, alternate,
            ),
            edge_record(
                "invoice-v2", PlannedEdgeKind.CALL_TARGET, "call:tax/direct",
                PlannedEdgeOperation.REWRITE, "calls", "calls", old_callee, new_callee,
                old_required=self.contract, new_required=alternate,
            ),
        )
        old_decl_edges = _declaration_edges(self.store, old_callee)
        new_decl_edges = _declaration_edges(self.store, new_callee)
        self.assertEqual(old_decl_edges[("reference", "provided-contract")],
                         ("provides_contract", self.contract, None, None))
        self.assertEqual(new_decl_edges[("reference", "provided-contract")],
                         ("provides_contract", alternate, None, None))
        self.assertTrue(_edge_record_matches(
            edges[0], "tax-v2", PlannedEdgeKind.TYPED_REFERENCE,
            "provided-contract", old_decl_edges[("reference", "provided-contract")],
            new_decl_edges[("reference", "provided-contract")],
        ))
        result = self.audit(
            baseline, candidate,
            actions=(action(old_callee), rewrite_action(old_caller)),
            decisions=decisions, outputs=outputs, edge_changes=edges,
        )
        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.edge_changes[0].baseline_required_contract_hash, self.contract)
        self.assertEqual(result.edge_changes[0].candidate_required_contract_hash, alternate)


if __name__ == "__main__":
    unittest.main()
