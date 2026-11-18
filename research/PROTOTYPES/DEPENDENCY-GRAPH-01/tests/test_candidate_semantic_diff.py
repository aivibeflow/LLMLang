import hashlib
import json
import unittest

from src.candidate_semantic_diff import audit_candidate_semantic_diff
from src.impact_planning import (
    ActionKind, CallSiteDecision, CallSiteDisposition, ImpactPlan, PlannedAction,
    OutputOperation, PlannedOutput, PlannedEdgeKind, PlannedEdgeOperation,
    PlannedEdgeChange, assign_planned_action_ids, compute_impact_plan_id,
)
from src.semantic_dependency_index import FORMAT, SCHEMA_VERSION, publish_declaration, validate_declaration
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


def site(target_hash, required_contract_hash):
    return [{
        "call_site_id": "call:tax",
        "targets": [{
            "target_id": "direct",
            "target_hash": target_hash,
            "condition": None,
            "required_contract_hash": required_contract_hash,
        }],
    }]


def action(value_hash):
    return PlannedAction(ActionKind.REBUILD, value_hash, "covered by approved CIP")


def rewrite_action(value_hash):
    return PlannedAction(ActionKind.REWRITE_CALL_SITE, value_hash, "rewrite exact planned call site")


class CandidateSemanticDiffTests(unittest.TestCase):
    def setUp(self):
        self.store = ContentStore()
        self.contract_hash = publish_declaration(
            self.store, declaration("contract", "contract:tax", {"name": "TaxContract"})
        )
        provided = [{"reference_id": "provided-contract", "relation": "provides_contract",
                     "target_hash": self.contract_hash, "target_kind": "contract"}]
        self.old_callee = publish_declaration(
            self.store, declaration("function", "tax:v1", {"rule": "old"},
                                    references=provided)
        )
        self.new_callee = publish_declaration(
            self.store, declaration("function", "tax:v2", {"rule": "new"},
                                    references=provided)
        )
        self.old_caller = publish_declaration(
            self.store, declaration("function", "invoice:v1", {"body": "old"},
                                    call_sites=site(self.old_callee, self.contract_hash))
        )
        self.new_caller = publish_declaration(
            self.store, declaration("function", "invoice:v2", {"body": "new"},
                                    call_sites=site(self.new_callee, self.contract_hash))
        )

    def plan(self, baseline, candidate, actions=(), decisions=(),
             outputs=None, edge_changes=None):
        try:
            before = {key: value for key, value in baseline.selections
                      if isinstance(key, str) and key}
        except (TypeError, ValueError):
            before = {}
        try:
            after = {key: value for key, value in candidate.selections
                     if isinstance(key, str) and key}
        except (TypeError, ValueError):
            after = {}

        if outputs is None:
            output_rows = []
            for key in sorted(set(before) | set(after)):
                old_hash, new_hash = before.get(key), after.get(key)
                if old_hash == new_hash:
                    continue
                operation = (OutputOperation.ADD if old_hash is None else
                             OutputOperation.REMOVE if new_hash is None else
                             OutputOperation.REPLACE)
                if operation is OutputOperation.REMOVE:
                    kind = payload_digest = None
                else:
                    value = self.store.get(new_hash)
                    declaration_value = validate_declaration(value.payload)
                    kind = declaration_value["kind"]
                    payload_digest = hashlib.sha256(canonical_bytes({
                        "declaration_id": declaration_value["declaration_id"],
                        "content": declaration_value["content"],
                    })).hexdigest()
                output_rows.append(PlannedOutput(
                    "output:" + key, key, operation, old_hash, kind, payload_digest,
                    "test fixture exact output", "evidence:output:" + key,
                ))
            outputs = tuple(output_rows)

        def declaration_edges(value_hash):
            value = self.store.get(value_hash)
            declaration_value = validate_declaration(value.payload)
            edges = {}
            for row in declaration_value["references"]:
                edges[("reference", row["reference_id"])] = (
                    row["relation"], row["target_hash"], row["condition"], None
                )
            for site_row in declaration_value["call_sites"]:
                for target in site_row["targets"]:
                    edges[("call", site_row["call_site_id"] + "/" + target["target_id"])] = (
                        "calls", target["target_hash"], target["condition"],
                        target["required_contract_hash"],
                    )
            return edges

        if edge_changes is None:
            edge_rows = []
            output_by_key = {item.logical_key: item for item in outputs}
            for key in sorted(set(before) | set(after)):
                old_hash, new_hash = before.get(key), after.get(key)
                if old_hash == new_hash:
                    continue
                if new_hash is None and old_hash in after.values():
                    continue
                old_edge_hash = old_hash or (
                    new_hash if new_hash in before.values() else None
                )
                old_edges = declaration_edges(old_edge_hash) if old_edge_hash else {}
                new_edges = declaration_edges(new_hash) if new_hash else {}
                output = output_by_key.get(key)
                if output is None:
                    continue
                for edge_key in sorted(set(old_edges) | set(new_edges)):
                    old_row, new_row = old_edges.get(edge_key), new_edges.get(edge_key)
                    if old_row == new_row:
                        continue
                    edge_kind, edge_id = edge_key
                    old_rel, old_target, old_cond, old_req = old_row if old_row else (None, None, None, None)
                    new_rel, new_target, new_cond, new_req = new_row if new_row else (None, None, None, None)
                    if old_row is None:
                        operation = PlannedEdgeOperation.ADD
                    elif new_row is None:
                        operation = PlannedEdgeOperation.REMOVE
                    elif (old_rel, old_target, old_req) == (new_rel, new_target, new_req) and old_cond != new_cond:
                        operation = PlannedEdgeOperation.CONDITION
                    else:
                        operation = PlannedEdgeOperation.REWRITE
                    edge_rows.append(PlannedEdgeChange(
                        output.output_id,
                        PlannedEdgeKind.TYPED_REFERENCE if edge_kind == "reference" else PlannedEdgeKind.CALL_TARGET,
                        edge_id, operation, old_rel, new_rel, old_target, new_target,
                        old_cond, new_cond, "test fixture exact edge", "evidence:edge",
                        old_req, new_req,
                    ))
            edge_changes = tuple(edge_rows)

        identified_actions = assign_planned_action_ids(tuple(actions))
        provisional = ImpactPlan(
            "", baseline.root_hash, candidate.root_hash, "policy:test",
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

    def test_changed_selection_requires_exact_hash_action_coverage(self):
        revised = publish_declaration(
            self.store, declaration("function", "invoice:v1.1", {"body": "revised"},
                                    call_sites=site(self.old_callee, self.contract_hash))
        )
        baseline = make_snapshot({"contract": self.contract_hash, "invoice": self.old_caller, "tax": self.old_callee})
        candidate = make_snapshot({"contract": self.contract_hash, "invoice": revised, "tax": self.old_callee})
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
        baseline = make_snapshot({"contract": self.contract_hash, "old": self.old_callee})
        candidate = make_snapshot({"contract": self.contract_hash, "new": self.new_callee})
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
        baseline = make_snapshot({"contract": self.contract_hash, "tax": self.old_callee, "invoice": self.old_caller})
        candidate = make_snapshot({"contract": self.contract_hash, "tax": self.new_callee, "invoice": self.new_caller})
        decision = CallSiteDecision(
            self.old_caller, "call:tax", "direct", self.old_callee,
            CallSiteDisposition.MIGRATE, self.new_callee, self.new_caller,
            "new tax contract", "evidence:compatibility",
            self.contract_hash, "PROVEN",
            None, "", "output:invoice",
        )
        plan = self.plan(
            baseline, candidate,
            actions=(action(self.old_callee), rewrite_action(self.old_caller)),
            decisions=(decision,),
        )
        result = audit_candidate_semantic_diff(self.store, baseline, candidate, plan)
        self.assertTrue(result.valid, result.errors)

    def test_changed_callee_requires_decisions_for_unchanged_incoming_callers(self):
        baseline = make_snapshot({"contract": self.contract_hash, "tax": self.old_callee, "invoice": self.old_caller})
        candidate = make_snapshot({
            "contract": self.contract_hash,
            "tax": self.new_callee,
            "legacy-tax": self.old_callee,
            "invoice": self.old_caller,
        })
        decision = CallSiteDecision(
            self.old_caller, "call:tax", "direct", self.old_callee,
            CallSiteDisposition.PRESERVE, self.old_callee, self.old_caller,
            "retain legacy caller behavior", "evidence:preservation",
            self.contract_hash, self.contract_hash, self.contract_hash, "PROVEN",
        )
        result = audit_candidate_semantic_diff(
            self.store, baseline, candidate,
            self.plan(baseline, candidate,
                      actions=(action(self.old_callee), action(self.new_callee)),
                      decisions=(decision,)),
        )
        self.assertTrue(result.valid, result.errors)

    def test_changed_callee_with_omitted_incoming_decision_is_rejected(self):
        baseline = make_snapshot({"contract": self.contract_hash, "tax": self.old_callee, "invoice": self.old_caller})
        candidate = make_snapshot({
            "contract": self.contract_hash,
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
        baseline = make_snapshot({"contract": self.contract_hash, "tax": self.old_callee, "invoice": self.old_caller})
        candidate = make_snapshot({"contract": self.contract_hash, "tax": self.new_callee, "invoice": self.new_caller})
        result = audit_candidate_semantic_diff(
            self.store, baseline, candidate,
            self.plan(baseline, candidate,
                      actions=(action(self.old_callee), rewrite_action(self.old_caller))),
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("path-bound CIP decision" in error or "unique exact CIP decision" in error
                            for error in result.errors))

    def test_decision_cannot_claim_a_different_candidate_target(self):
        baseline = make_snapshot({"tax": self.old_callee, "invoice": self.old_caller})
        candidate = make_snapshot({"tax": self.new_callee, "invoice": self.new_caller})
        decision = CallSiteDecision(
            self.old_caller, "call:tax", "direct", self.old_callee,
            CallSiteDisposition.MIGRATE, self.old_callee, self.new_caller,
            "wrong target", "evidence:compatibility",
            self.contract_hash, self.contract_hash, self.contract_hash, "PROVEN",
            None, "", "output:invoice",
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

    def test_call_site_required_contract_change_is_visible_and_rejected(self):
        alternate_contract = publish_declaration(
            self.store, declaration("contract", "contract:tax-alternate", {"name": "Alternate"})
        )
        changed_requirement = publish_declaration(
            self.store, declaration(
                "function", "invoice:changed-requirement", {"body": "same"},
                call_sites=site(self.old_callee, alternate_contract),
            )
        )
        baseline = make_snapshot({"contract": self.contract_hash, "invoice": self.old_caller, "tax": self.old_callee})
        candidate = make_snapshot({"contract": self.contract_hash, "alternate": alternate_contract,
                                   "invoice": changed_requirement, "tax": self.old_callee})
        result = audit_candidate_semantic_diff(
            self.store, baseline, candidate,
            self.plan(baseline, candidate, actions=(action(self.old_caller),)),
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("required-contract change" in error for error in result.errors))
        edge = next(row for row in result.edge_changes if row.edge_kind == "call")
        self.assertEqual(edge.baseline_required_contract_hash, self.contract_hash)
        self.assertEqual(edge.candidate_required_contract_hash, alternate_contract)

    def test_typed_reference_change_is_rejected(self):
        contract = publish_declaration(
            self.store, declaration("contract", "contract:invoice")
        )
        old = publish_declaration(
            self.store, declaration(
                "function", "invoice:ref-old", {"body": "same"},
                call_sites=site(self.old_callee, self.contract_hash),
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
                call_sites=site(self.old_callee, self.contract_hash),
            )
        )
        baseline = make_snapshot({"contract": self.contract_hash, "extra-contract": contract,
                                   "invoice": old, "tax": self.old_callee})
        candidate = make_snapshot({"contract": self.contract_hash, "extra-contract": contract,
                                   "invoice": new, "tax": self.old_callee})
        result = audit_candidate_semantic_diff(
            self.store, baseline, candidate,
            self.plan(baseline, candidate, actions=(action(old),), edge_changes=()),
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
