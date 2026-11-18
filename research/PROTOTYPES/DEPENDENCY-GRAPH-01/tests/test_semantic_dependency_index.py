import unittest

from src.semantic_graph import ContentStore, make_snapshot
from src.semantic_dependency_index import (
    FORMAT, SCHEMA_VERSION, EXTRACTOR_ID, CompletenessStatus, ReverseLookupEvidence,
    audit_snapshot_incoming_independently,
    SemanticObjectError, dependency_edge_set_digest, query_snapshot_incoming,
    build_dependency_index, build_snapshot_dependency_index, publish_declaration, validate_declaration,
)


def declaration(kind, declaration_id, content=None, **extra):
    return {
        "format": FORMAT,
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "declaration_id": declaration_id,
        "content": content or {},
        **extra,
    }


class SemanticDependencyIndexTests(unittest.TestCase):
    def setUp(self):
        self.store = ContentStore()
        self.i32 = publish_declaration(self.store, declaration("type", "type:i32", {"name": "i32"}))
        self.tax_contract = publish_declaration(
            self.store, declaration("contract", "contract:tax", {"name": "TaxContract"},
                                    references=[{"reference_id": "input-type", "relation": "uses_type",
                                                 "target_hash": self.i32, "target_kind": "type"}])
        )
        self.effect = publish_declaration(self.store, declaration("effect", "effect:read-clock", {"name": "ReadClock"}))
        self.old_callee = publish_declaration(
            self.store, declaration("function", "fn:tax:v1", {"body": "old"},
                references=[{"reference_id": "provided-contract", "relation": "provides_contract",
                             "target_hash": self.tax_contract, "target_kind": "contract"}])
        )
        self.new_callee = publish_declaration(
            self.store, declaration("function", "fn:tax:v2", {"body": "new"},
                references=[{"reference_id": "provided-contract", "relation": "provides_contract",
                             "target_hash": self.tax_contract, "target_kind": "contract"}])
        )

    def test_call_sites_have_stable_distinct_edge_ids(self):
        caller = publish_declaration(self.store, declaration(
            "function", "fn:invoice:v1", {"body": "invoice"},
            call_sites=[
                {"call_site_id": "call:subtotal-tax", "targets": [
                    {"target_id": "direct", "target_hash": self.old_callee, "condition": None, "required_contract_hash": self.tax_contract}]},
                {"call_site_id": "call:final-tax", "targets": [
                    {"target_id": "direct", "target_hash": self.new_callee, "condition": None, "required_contract_hash": self.tax_contract}]},
            ],
        ))
        edges = [edge for edge in build_dependency_index(self.store).outgoing(caller)
                 if edge.relation == "calls"]
        self.assertEqual({edge.edge_id for edge in edges},
                         {"call:subtotal-tax/direct", "call:final-tax/direct"})
        self.assertEqual({edge.target_hash for edge in edges},
                         {self.old_callee, self.new_callee})
        self.assertTrue(all(edge.required_contract_hash == self.tax_contract for edge in edges))
        self.assertTrue(all(edge.provided_contract_hash == self.tax_contract for edge in edges))

    def test_conditional_dispatch_preserves_each_exact_target_and_condition(self):
        caller = publish_declaration(self.store, declaration(
            "operation", "op:route-tax", {"body": "dispatch"},
            call_sites=[{"call_site_id": "call:dispatch", "targets": [
                {"target_id": "business", "target_hash": self.old_callee,
                 "condition": "jurisdiction == legacy", "required_contract_hash": self.tax_contract},
                {"target_id": "consumer", "target_hash": self.new_callee,
                 "condition": "jurisdiction == current", "required_contract_hash": self.tax_contract},
            ]}],
        ))
        edges = [edge for edge in build_dependency_index(self.store).outgoing(caller)
                 if edge.relation == "calls"]
        self.assertEqual(len(edges), 2)
        self.assertEqual({edge.condition for edge in edges},
                         {"jurisdiction == legacy", "jurisdiction == current"})

    def test_reverse_index_keeps_call_site_context(self):
        caller = publish_declaration(self.store, declaration(
            "function", "fn:caller", {"body": "x"},
            call_sites=[{"call_site_id": "call:one", "targets": [
                {"target_id": "primary", "target_hash": self.old_callee, "condition": None, "required_contract_hash": self.tax_contract}]}],
        ))
        incoming = build_dependency_index(self.store).incoming(self.old_callee)
        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming[0].source_hash, caller)
        self.assertEqual(incoming[0].edge_id, "call:one/primary")

    def test_snapshot_scoped_reverse_index_excludes_historical_callers(self):
        old_caller = publish_declaration(self.store, declaration(
            "function", "fn:shared:old", {"body": "shared"},
            call_sites=[{"call_site_id": "call:tax", "targets": [
                {"target_id": "direct", "target_hash": self.old_callee, "condition": None, "required_contract_hash": self.tax_contract}]}],
        ))
        stale_caller = publish_declaration(self.store, declaration(
            "function", "fn:shared:stale", {"body": "older shared body"},
            call_sites=[{"call_site_id": "call:tax", "targets": [
                {"target_id": "direct", "target_hash": self.old_callee, "condition": None, "required_contract_hash": self.tax_contract}]}],
        ))
        new_caller = publish_declaration(self.store, declaration(
            "function", "fn:shared:new", {"body": "shared"},
            call_sites=[{"call_site_id": "call:tax", "targets": [
                {"target_id": "direct", "target_hash": self.new_callee, "condition": None, "required_contract_hash": self.tax_contract}]}],
        ))
        snapshot = make_snapshot({
            "callee": self.new_callee,
            "preserving-consumer": old_caller,
            "migrating-consumer": new_caller,
        })

        index = build_snapshot_dependency_index(self.store, snapshot)

        self.assertEqual(index.snapshot_root, snapshot.root_hash)
        self.assertEqual({edge.source_hash for edge in index.incoming(self.old_callee)}, {old_caller})
        self.assertNotIn(stale_caller, {edge.source_hash for edge in index.incoming(self.old_callee)})
        self.assertEqual({edge.source_hash for edge in index.incoming(self.new_callee)}, {new_caller})
        self.assertNotIn(old_caller, {edge.source_hash for edge in index.incoming(self.new_callee)})

    def test_snapshot_scoped_index_rejects_missing_selected_object(self):
        snapshot = make_snapshot({"missing": "not-in-store"})
        with self.assertRaises(KeyError):
            build_snapshot_dependency_index(self.store, snapshot)


    def _reverse_query_fixture(self):
        caller = publish_declaration(self.store, declaration(
            "function", "fn:reverse-query-caller", {"body": "x"},
            call_sites=[{"call_site_id": "call:tax", "targets": [
                {"target_id": "direct", "target_hash": self.old_callee, "condition": None, "required_contract_hash": self.tax_contract}]}],
        ))
        return make_snapshot({"callee": self.old_callee, "caller": caller})

    def _reverse_evidence(self, snapshot, edge_digest, **overrides):
        values = {
            "evidence_id": "audit:reverse:001", "snapshot_root": snapshot.root_hash,
            "target_hash": self.old_callee, "scope": "all-static-call-sites",
            "index_schema_version": SCHEMA_VERSION, "extractor_id": EXTRACTOR_ID,
            "edge_set_digest": edge_digest,
            "status": CompletenessStatus.SUPPORTED_WITHIN_SCOPE,
            "observation_model_id": "static-call-model/1",
            "assumptions": ("all declarations in selected snapshot were elaborated",),
            "exclusions": ("runtime reflection",),
        }
        values.update(overrides)
        return ReverseLookupEvidence(**values)

    def test_independent_payload_scan_produces_snapshot_bound_evidence(self):
        snapshot = self._reverse_query_fixture()
        result = query_snapshot_incoming(self.store, snapshot, self.old_callee,
                                         "all-static-call-sites")
        evidence = audit_snapshot_incoming_independently(self.store, snapshot, result)
        self.assertEqual(evidence.status, CompletenessStatus.SUPPORTED_WITHIN_SCOPE)
        checked = query_snapshot_incoming(self.store, snapshot, self.old_callee,
                                          "all-static-call-sites", evidence)
        self.assertEqual(checked.completeness_status, CompletenessStatus.SUPPORTED_WITHIN_SCOPE)
        self.assertEqual(checked.evidence_id, evidence.evidence_id)

    def test_independent_payload_scan_detects_missing_reverse_index_edge(self):
        from dataclasses import replace
        snapshot = self._reverse_query_fixture()
        result = query_snapshot_incoming(self.store, snapshot, self.old_callee,
                                         "all-static-call-sites")
        incomplete = replace(result, edges=(), edge_set_digest=dependency_edge_set_digest(()))
        evidence = audit_snapshot_incoming_independently(self.store, snapshot, incomplete)
        self.assertEqual(evidence.status, CompletenessStatus.GAP_FOUND)
        self.assertTrue(any(item.startswith("missing-index-edge:") for item in evidence.discrepancies))

    def test_reverse_query_without_evidence_is_not_checked(self):
        snapshot = self._reverse_query_fixture()
        result = query_snapshot_incoming(self.store, snapshot, self.old_callee,
                                         "all-static-call-sites")
        self.assertEqual(result.completeness_status, CompletenessStatus.NOT_CHECKED)
        self.assertEqual(len(result.edges), 1)
        self.assertIsNone(result.evidence_id)

    def test_reverse_query_accepts_exact_scope_bound_evidence(self):
        snapshot = self._reverse_query_fixture()
        edges = build_snapshot_dependency_index(self.store, snapshot).incoming(self.old_callee)
        evidence = self._reverse_evidence(snapshot, dependency_edge_set_digest(edges))
        result = query_snapshot_incoming(self.store, snapshot, self.old_callee,
                                         "all-static-call-sites", evidence)
        self.assertEqual(result.completeness_status, CompletenessStatus.SUPPORTED_WITHIN_SCOPE)
        self.assertEqual(result.evidence_id, evidence.evidence_id)
        self.assertIn("only within", result.reason)

    def test_reverse_query_rejects_stale_snapshot_evidence(self):
        snapshot = self._reverse_query_fixture()
        edges = build_snapshot_dependency_index(self.store, snapshot).incoming(self.old_callee)
        evidence = self._reverse_evidence(
            snapshot, dependency_edge_set_digest(edges), snapshot_root="stale-root")
        result = query_snapshot_incoming(self.store, snapshot, self.old_callee,
                                         "all-static-call-sites", evidence)
        self.assertEqual(result.completeness_status, CompletenessStatus.UNKNOWN)

    def test_reverse_query_rejects_wrong_extractor_or_edge_digest(self):
        snapshot = self._reverse_query_fixture()
        edges = build_snapshot_dependency_index(self.store, snapshot).incoming(self.old_callee)
        digest = dependency_edge_set_digest(edges)
        for overrides in ({"extractor_id": "different-extractor/1"},
                          {"edge_set_digest": "wrong-digest"}):
            evidence = self._reverse_evidence(snapshot, digest, **overrides)
            result = query_snapshot_incoming(self.store, snapshot, self.old_callee,
                                             "all-static-call-sites", evidence)
            self.assertEqual(result.completeness_status, CompletenessStatus.UNKNOWN)

    def test_reverse_query_preserves_gap_status_and_discrepancies(self):
        snapshot = self._reverse_query_fixture()
        edges = build_snapshot_dependency_index(self.store, snapshot).incoming(self.old_callee)
        evidence = self._reverse_evidence(
            snapshot, dependency_edge_set_digest(edges),
            status=CompletenessStatus.GAP_FOUND,
            discrepancies=("unresolved dynamic dispatch candidate",))
        result = query_snapshot_incoming(self.store, snapshot, self.old_callee,
                                         "all-static-call-sites", evidence)
        self.assertEqual(result.completeness_status, CompletenessStatus.GAP_FOUND)
        self.assertEqual(result.discrepancies, ("unresolved dynamic dispatch candidate",))

    def test_supported_evidence_cannot_hide_discrepancies(self):
        with self.assertRaises(ValueError):
            ReverseLookupEvidence(
                evidence_id="audit", snapshot_root="root", target_hash="target",
                scope="scope", index_schema_version=1, extractor_id=EXTRACTOR_ID,
                edge_set_digest="digest", status=CompletenessStatus.SUPPORTED_WITHIN_SCOPE,
                observation_model_id="model", discrepancies=("unresolved",))

    def test_gap_evidence_requires_a_discrepancy(self):
        with self.assertRaises(ValueError):
            ReverseLookupEvidence(
                evidence_id="audit", snapshot_root="root", target_hash="target",
                scope="scope", index_schema_version=1, extractor_id=EXTRACTOR_ID,
                edge_set_digest="digest", status=CompletenessStatus.GAP_FOUND,
                observation_model_id="model")

    def test_typed_references_validate_target_kind(self):
        impl = publish_declaration(self.store, declaration(
            "implementation", "impl:tax", {"body": "impl"},
            references=[
                {"reference_id": "contract-binding", "relation": "implements_contract",
                 "target_hash": self.tax_contract, "target_kind": "contract"},
                {"reference_id": "clock-effect", "relation": "uses_effect",
                 "target_hash": self.effect, "target_kind": "effect"},
            ],
        ))
        edges = build_dependency_index(self.store).outgoing(impl)
        self.assertEqual({edge.relation for edge in edges},
                         {"implements_contract", "uses_effect"})

    def test_rejects_unknown_or_ambiguous_schema_fields(self):
        bad = declaration("function", "fn:bad", {"body": "x"}, calls=[self.old_callee])
        with self.assertRaises(SemanticObjectError):
            validate_declaration(bad)

    def test_rejects_duplicate_call_site_and_target_ids(self):
        bad = declaration("function", "fn:bad", {"body": "x"}, call_sites=[
            {"call_site_id": "same", "targets": [
                {"target_id": "x", "target_hash": self.old_callee, "condition": None, "required_contract_hash": self.tax_contract},
                {"target_id": "x", "target_hash": self.new_callee, "condition": None, "required_contract_hash": self.tax_contract}]}
        ])
        with self.assertRaises(SemanticObjectError):
            validate_declaration(bad)

    def test_rejects_wrong_target_kind(self):
        bad = declaration("function", "fn:bad", {"body": "x"}, references=[
            {"reference_id": "wrong", "relation": "uses_type",
             "target_hash": self.tax_contract, "target_kind": "contract"}
        ])
        with self.assertRaises(SemanticObjectError):
            publish_declaration(self.store, bad)

    def test_call_site_requirement_is_a_hash_relevant_contract_dependency(self):
        caller_a = publish_declaration(self.store, declaration(
            "function", "fn:requirement-a", {"body": "x"},
            call_sites=[{"call_site_id": "call:tax", "targets": [{
                "target_id": "direct", "target_hash": self.old_callee, "condition": None,
                "required_contract_hash": self.tax_contract}]}],
        ))
        alternate_contract = publish_declaration(
            self.store, declaration("contract", "contract:tax-alternate", {"name": "Alternate"})
        )
        caller_b = publish_declaration(self.store, declaration(
            "function", "fn:requirement-b", {"body": "x"},
            call_sites=[{"call_site_id": "call:tax", "targets": [{
                "target_id": "direct", "target_hash": self.old_callee, "condition": None,
                "required_contract_hash": alternate_contract}]}],
        ))
        self.assertNotEqual(caller_a, caller_b)
        edge = next(e for e in build_dependency_index(self.store).outgoing(caller_a)
                    if e.relation == "calls")
        self.assertEqual(edge.required_contract_hash, self.tax_contract)
        self.assertEqual(edge.provided_contract_hash, self.tax_contract)

    def test_required_and_provided_contracts_are_both_reverse_indexed(self):
        caller = publish_declaration(self.store, declaration(
            "function", "fn:contract-index-caller", {"body": "x"},
            call_sites=[{"call_site_id": "call:tax", "targets": [{
                "target_id": "direct", "target_hash": self.old_callee, "condition": None,
                "required_contract_hash": self.tax_contract}]}],
        ))
        incoming = build_dependency_index(self.store).incoming(self.tax_contract)
        relations = {(edge.source_hash, edge.relation, edge.edge_id) for edge in incoming}
        self.assertIn((self.old_callee, "provides_contract", "provided-contract"), relations)
        self.assertIn((caller, "requires_contract", "call:tax/direct/required-contract"), relations)

    def test_rejects_call_target_without_required_contract(self):
        bad = declaration("function", "fn:missing-requirement", {"body": "x"},
            call_sites=[{"call_site_id": "call:tax", "targets": [{
                "target_id": "direct", "target_hash": self.old_callee, "condition": None}]}])
        with self.assertRaises(SemanticObjectError):
            validate_declaration(bad)

    def test_rejects_callee_without_exactly_one_provided_contract(self):
        no_contract = publish_declaration(
            self.store, declaration("function", "fn:no-contract", {"body": "x"})
        )
        bad = declaration("function", "fn:caller-no-contract", {"body": "x"},
            call_sites=[{"call_site_id": "call:bad", "targets": [{
                "target_id": "direct", "target_hash": no_contract, "condition": None,
                "required_contract_hash": self.tax_contract}]}])
        with self.assertRaises(SemanticObjectError):
            publish_declaration(self.store, bad)

    def test_exact_target_revision_is_part_of_caller_hash(self):
        caller_v1 = publish_declaration(self.store, declaration(
            "function", "fn:caller", {"body": "x"},
            call_sites=[{"call_site_id": "call:tax", "targets": [
                {"target_id": "direct", "target_hash": self.old_callee, "condition": None, "required_contract_hash": self.tax_contract}]}],
        ))
        caller_v2 = publish_declaration(self.store, declaration(
            "function", "fn:caller", {"body": "x"},
            call_sites=[{"call_site_id": "call:tax", "targets": [
                {"target_id": "direct", "target_hash": self.new_callee, "condition": None, "required_contract_hash": self.tax_contract}]}],
        ))
        self.assertNotEqual(caller_v1, caller_v2)
        self.assertIn(self.old_callee, self.store)
        self.assertIn(self.new_callee, self.store)


if __name__ == "__main__":
    unittest.main()
