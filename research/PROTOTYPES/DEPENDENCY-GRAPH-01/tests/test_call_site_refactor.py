from dataclasses import replace
import unittest

from src.call_site_refactor import (
    BoundaryCheck, CallRef, InlineRef, RefactorAudit, RefactorError, RefactorPlan, Transfer, audit_refactor,
)
from src.identity_lifecycle import Binding, Lineage, Relation, Slot, State, compare
from src.semantic_dependency_index import FORMAT, SCHEMA_VERSION, publish_declaration
from src.semantic_graph import ContentStore, make_snapshot


class RefactorExperiment(unittest.TestCase):
    def setUp(self):
        self.store = ContentStore()
        self.required = self.publish("contract", "required", {"finite_outputs": [
            {"input": 0, "outputs": [2, 3]},
            {"input": 3, "outputs": [5, 6]},
        ]})
        self.different_contract = self.publish("contract", "different", {"finite_outputs": [
            {"input": 0, "outputs": [2]},
            {"input": 3, "outputs": [5]},
        ]})
        self.leaf = self.publish("function", "leaf", {"add_offset": 2}, provided=self.different_contract)
        self.caller = self.publish("function", "caller", {"forward_input_to": "old/direct"},
                                   calls=[self.call("old", self.leaf)])
        self.base = make_snapshot({"app/main": self.caller})
        self.source = CallRef("app/main", self.caller, "old/direct")

    def publish(self, kind, name, content, *, provided=None, calls=()):
        refs = [] if provided is None else [{"reference_id": "provided", "relation": "provides_contract",
                                             "target_hash": provided, "target_kind": "contract"}]
        return publish_declaration(self.store, {
            "format": FORMAT, "schema_version": SCHEMA_VERSION, "kind": kind,
            "declaration_id": name, "content": content, "references": refs, "call_sites": list(calls),
        })

    def call(self, name, target, *, required=None, condition=None):
        return {"call_site_id": name, "targets": [{"target_id": "direct", "target_hash": target,
                                                    "required_contract_hash": required or self.required,
                                                    "condition": condition}]}

    def extracted(self, *, target=None, required=None, condition=None):
        helper = self.publish("function", "helper", {"forward_input_to": "inside/direct"},
                              provided=self.required, calls=[self.call(
                                  "inside", target or self.leaf, required=required, condition=condition,
                              )])
        wrapper = self.publish("function", "caller", {"forward_input_to": "bridge/direct"},
                               calls=[self.call("bridge", helper)])
        candidate = make_snapshot({"app/main": wrapper, "shared/helper": helper}, (self.base.root_hash,))
        moved = CallRef("shared/helper", helper, "inside/direct")
        bridge = CallRef("app/main", wrapper, "bridge/direct")
        plan = RefactorPlan(self.base.root_hash, candidate.root_hash,
                            (Transfer(self.source, (moved,)),), (bridge,))
        return candidate, moved, plan

    def inlined(self, offset=2):
        caller = self.publish("function", "caller", {"inline_input_offset": {"region": "r", "offset": offset}})
        candidate = make_snapshot({"app/main": caller}, (self.base.root_hash,))
        region = InlineRef("app/main", caller, "r")
        return candidate, region, RefactorPlan(self.base.root_hash, candidate.root_hash,
                                               (Transfer(self.source, (region,)),))

    def test_extraction_keeps_binding_under_all_three_lineage_policies(self):
        candidate, moved, plan = self.extracted()
        old_slot = Slot(self.source.selection, self.source.edge_id)
        new_slot = Slot(moved.selection, moved.edge_id)
        old = State((Binding(old_slot, self.leaf, self.source.caller_hash, "old", "managed-id"),))
        new = State((Binding(new_slot, self.leaf, moved.caller_hash, "inside", "managed-id"),))
        link = Relation("continue", (old_slot,), (new_slot,))
        lineage = Lineage(old.revision, new.revision, (link,))
        for policy in ("stable-id", "scoped-slot", "lineage"):
            with self.subTest(policy=policy):
                implicit = compare(self.store, old, new, policy).relations
                self.assertEqual(implicit, (link,) if policy == "stable-id" else ())
                self.assertEqual(compare(self.store, old, new, policy, lineage=lineage).relations, (link,))
                self.assertEqual(audit_refactor(self.store, self.base, candidate, plan),
                                 RefactorAudit((BoundaryCheck(self.source, moved, "exact-call-binding"),),
                                               plan.new_calls))

    def test_changed_target_condition_or_required_contract_cannot_claim_exact_binding(self):
        variant = self.publish("function", "leaf-v2", {"add_offset": 2}, provided=self.different_contract)
        for change in ({"target": variant}, {"required": self.different_contract}, {"condition": "flag"}):
            with self.subTest(change=change):
                candidate, _, plan = self.extracted(**change)
                with self.assertRaisesRegex(RefactorError, "changed target, guard, or required contract"):
                    audit_refactor(self.store, self.base, candidate, plan)

    def test_all_added_edges_and_all_removed_paths_need_an_explicit_account(self):
        candidate, _, plan = self.extracted()
        with self.assertRaisesRegex(RefactorError, "added call edge has no classification"):
            audit_refactor(self.store, self.base, candidate, replace(plan, new_calls=()))
        forked_base = make_snapshot({"app/main": self.caller, "app/other": self.caller})
        rebound = replace(plan, baseline_root=forked_base.root_hash)
        with self.assertRaisesRegex(RefactorError, "removed call edge has no transfer"):
            audit_refactor(self.store, forked_base, candidate, rebound)

    def test_one_source_can_split_into_two_exact_candidate_occurrences(self):
        candidate, moved, plan = self.extracted()
        cloned = make_snapshot({**candidate.mapping, "shared/helper-copy": moved.caller_hash},
                               candidate.parent_roots)
        other = replace(moved, selection="shared/helper-copy")
        plan = replace(plan, candidate_root=cloned.root_hash,
                       transfers=(Transfer(self.source, (moved, other)),))
        audit = audit_refactor(self.store, self.base, cloned, plan)
        self.assertEqual(tuple(item.destination for item in audit.boundary_checks), (moved, other))
        repeated = replace(plan, transfers=(Transfer(self.source, (moved, moved)),))
        with self.assertRaisesRegex(RefactorError, "not a unique added call"):
            audit_refactor(self.store, self.base, cloned, repeated)

    def test_branch_import_cannot_reuse_a_plan_for_equal_selections_with_another_parent(self):
        candidate, _, plan = self.extracted()
        parent = make_snapshot({"app/main": self.caller}, (self.base.root_hash,))
        imported = make_snapshot(candidate.mapping, (parent.root_hash,))
        self.assertEqual(imported.selections, candidate.selections)
        self.assertNotEqual(imported.root_hash, candidate.root_hash)
        with self.assertRaisesRegex(RefactorError, "another Snapshot pair"):
            audit_refactor(self.store, self.base, imported, plan)
        forged = replace(imported, root_hash=candidate.root_hash)
        with self.assertRaisesRegex(RefactorError, "root or selections are inconsistent"):
            audit_refactor(self.store, self.base, forged, plan)

    def test_inline_discharges_the_call_only_for_the_checked_body_and_domain(self):
        candidate, region, plan = self.inlined()
        self.assertEqual(audit_refactor(self.store, self.base, candidate, plan),
                         RefactorAudit((BoundaryCheck(self.source, region, "finite-inline-equivalence", (0, 3)),),
                                       ()))
        invented = replace(plan, transfers=(Transfer(self.source, (replace(region, region="other"),)),))
        with self.assertRaisesRegex(RefactorError, "no matching executable inline body"):
            audit_refactor(self.store, self.base, candidate, invented)
        elsewhere = make_snapshot({"app/other": region.caller_hash}, (self.base.root_hash,))
        moved_body = replace(plan, candidate_root=elsewhere.root_hash,
                             transfers=(Transfer(self.source, (replace(region, selection="app/other"),)),))
        with self.assertRaisesRegex(RefactorError, "not a unique selected replacement"):
            audit_refactor(self.store, self.base, elsewhere, moved_body)

    def test_contract_conformance_alone_does_not_establish_equivalent_inline(self):
        for offset, diagnostic in ((3, "differs from baseline at input 0"),
                                   (4, "violates the required contract at input 0")):
            with self.subTest(offset=offset):
                candidate, _, plan = self.inlined(offset)
                with self.assertRaisesRegex(RefactorError, diagnostic):
                    audit_refactor(self.store, self.base, candidate, plan)


if __name__ == "__main__":
    unittest.main()
