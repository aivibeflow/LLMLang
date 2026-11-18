import unittest

from src.semantic_dependency_index import SnapshotIncomingResult

from src.impact_planning import (
    ActionKind, CallSiteDecision, CallSiteDisposition, CompletenessEvidence,
    CompletenessStatus, ImpactedArtifact, OutputOperation, PlannedOutput,
    NonInterferenceCertificate, PlanningError, audit_dependency_completeness,
    audit_snapshot_incoming, dependency_digest, no_action_is_justified, plan_impact,
)


class ImpactPlanningTests(unittest.TestCase):
    def evidence(self, artifact, declared, observed, scope="static-scope", current=True):
        return CompletenessEvidence(
            artifact_hash=artifact,
            declared_dependency_digest=dependency_digest(declared),
            scope=scope,
            method="static+dynamic-audit-v1",
            tool_id="audit-tool/1",
            observed_dependencies=frozenset(observed),
            current=current,
        )

    def test_missing_observed_dependency_is_gap(self):
        audit = audit_dependency_completeness(
            "artifact-A", {"input-1"}, "static-scope",
            self.evidence("artifact-A", {"input-1"}, {"input-1", "hidden-config"}),
        )
        self.assertEqual(audit.status, CompletenessStatus.GAP_FOUND)
        self.assertEqual(audit.missing_dependencies, ("hidden-config",))

    def test_matching_evidence_only_supports_declared_scope(self):
        audit = audit_dependency_completeness(
            "artifact-A", {"input-1"}, "static-scope",
            self.evidence("artifact-A", {"input-1"}, {"input-1"}),
        )
        self.assertEqual(audit.status, CompletenessStatus.SUPPORTED_WITHIN_SCOPE)
        self.assertIn("not a global completeness proof", audit.reason)

    def test_no_evidence_is_not_checked(self):
        audit = audit_dependency_completeness("artifact-A", {"input-1"}, "scope", None)
        self.assertEqual(audit.status, CompletenessStatus.NOT_CHECKED)

    def test_stale_evidence_is_unknown(self):
        audit = audit_dependency_completeness(
            "artifact-A", {"input-1"}, "static-scope",
            self.evidence("artifact-A", {"input-1"}, {"input-1"}, current=False),
        )
        self.assertEqual(audit.status, CompletenessStatus.UNKNOWN)

    def test_evidence_for_wrong_artifact_or_scope_is_unknown(self):
        evidence = self.evidence("other-artifact", {"input-1"}, {"input-1"})
        audit = audit_dependency_completeness(
            "artifact-A", {"input-1"}, "static-scope", evidence)
        self.assertEqual(audit.status, CompletenessStatus.UNKNOWN)

    def test_unknown_completeness_forces_full_validation_and_review(self):
        artifact = ImpactedArtifact("contract-A", "caller_contract", "requirement changed")
        audit = audit_dependency_completeness("contract-A", {"req-A"}, "scope", None)
        plan = plan_impact("base", "candidate", "policy-v1", [artifact], [audit], require_snapshot_evidence=False)
        kinds = {action.kind for action in plan.actions}
        self.assertIn(ActionKind.RE_DERIVE, kinds)
        self.assertIn(ActionKind.HUMAN_REVIEW, kinds)
        self.assertIn(ActionKind.FULL_REVALIDATION, kinds)

    def test_gap_forces_full_validation_even_when_targeted_actions_exist(self):
        artifact = ImpactedArtifact("tests-A", "test_suite", "contract changed")
        audit = audit_dependency_completeness(
            "tests-A", {"contract-A"}, "scope",
            self.evidence("tests-A", {"contract-A"}, {"contract-A", "schema-B"}, "scope"),
        )
        plan = plan_impact("base", "candidate", "policy-v1", [artifact], [audit], require_snapshot_evidence=False)
        kinds = [action.kind for action in plan.actions]
        self.assertIn(ActionKind.REGENERATE_TESTS, kinds)
        self.assertIn(ActionKind.RUN_TESTS, kinds)
        self.assertIn(ActionKind.FULL_REVALIDATION, kinds)

    def test_action_policy_distinguishes_regenerate_run_and_reprove(self):
        artifacts = [
            ImpactedArtifact("suite", "test_suite", "contract changed"),
            ImpactedArtifact("proof", "verification_record", "obligation changed"),
            ImpactedArtifact("code", "implementation", "source changed"),
        ]
        audits = [
            audit_dependency_completeness(a.artifact_hash, set(), "scope",
                self.evidence(a.artifact_hash, set(), set(), "scope"))
            for a in artifacts
        ]
        plan = plan_impact("base", "candidate", "policy-v1", artifacts, audits, require_snapshot_evidence=False)
        kinds = {action.kind for action in plan.actions}
        self.assertTrue({ActionKind.REGENERATE_TESTS, ActionKind.RUN_TESTS,
                         ActionKind.REPROVE, ActionKind.REBUILD}.issubset(kinds))
        self.assertNotIn(ActionKind.FULL_REVALIDATION, kinds)

    def test_unknown_artifact_kind_forces_conservative_actions(self):
        artifact = ImpactedArtifact("opaque", "unclassified_kind", "changed")
        audit = audit_dependency_completeness(
            "opaque", set(), "scope", self.evidence("opaque", set(), set(), "scope"))
        plan = plan_impact("base", "candidate", "policy-v1", [artifact], [audit], require_snapshot_evidence=False)
        kinds = {action.kind for action in plan.actions}
        self.assertIn(ActionKind.HUMAN_REVIEW, kinds)
        self.assertIn(ActionKind.FULL_REVALIDATION, kinds)

    def test_no_action_requires_exact_proven_certificate(self):
        cert = NonInterferenceCertificate(
            "artifact-A", "input-B", "public-output", "checker-v1", "PROVEN")
        self.assertTrue(no_action_is_justified(
            "artifact-A", "input-B", "public-output", cert))
        self.assertFalse(no_action_is_justified(
            "artifact-A", "input-C", "public-output", cert))
        self.assertFalse(no_action_is_justified(
            "artifact-A", "input-B", "internal-state", cert))

    def test_unproven_or_missing_certificate_never_justifies_skip(self):
        cert = NonInterferenceCertificate(
            "artifact-A", "input-B", "public-output", "checker-v1", "UNKNOWN")
        self.assertFalse(no_action_is_justified(
            "artifact-A", "input-B", "public-output", cert))
        self.assertFalse(no_action_is_justified(
            "artifact-A", "input-B", "public-output", None))

    def test_plan_identity_is_deterministic_and_policy_sensitive(self):
        artifact = ImpactedArtifact("clause", "formal_clause", "req changed")
        audit = audit_dependency_completeness(
            "clause", {"req"}, "scope",
            self.evidence("clause", {"req"}, {"req"}, "scope"))
        first = plan_impact("base", "candidate", "policy-v1", [artifact], [audit], require_snapshot_evidence=False)
        second = plan_impact("base", "candidate", "policy-v1", [artifact], [audit], require_snapshot_evidence=False)
        other_policy = plan_impact("base", "candidate", "policy-v2", [artifact], [audit], require_snapshot_evidence=False)
        self.assertEqual(first.plan_id, second.plan_id)
        self.assertNotEqual(first.plan_id, other_policy.plan_id)

    def test_snapshot_reverse_lookup_is_bound_into_impact_plan(self):
        result = SnapshotIncomingResult(
            snapshot_root="base", target_hash="contract-A", scope="all-static-call-sites",
            edges=(), edge_set_digest="edge-digest-1", index_schema_version=1,
            extractor_id="semantic-dependency-extractor/1",
            completeness_status=CompletenessStatus.SUPPORTED_WITHIN_SCOPE,
            reason="supported within declared scope", evidence_id="audit-001",
            discrepancies=(),
        )
        audit = audit_snapshot_incoming(result)
        artifact = ImpactedArtifact("contract-A", "caller_contract", "callee changed")
        plan = plan_impact("base", "candidate", "policy-v1", [artifact], [audit])
        self.assertEqual(plan.audit_statuses, (("contract-A", "SUPPORTED_WITHIN_SCOPE"),))
        self.assertEqual(plan.audit_bindings, (
            ("contract-A", "base", "contract-A", "all-static-call-sites", 1,
             "semantic-dependency-extractor/1", "audit-001", "edge-digest-1"),
        ))
        self.assertNotIn(ActionKind.FULL_REVALIDATION, {a.kind for a in plan.actions})

    def test_snapshot_result_without_evidence_remains_not_checked(self):
        result = SnapshotIncomingResult(
            snapshot_root="base", target_hash="contract-A", scope="scope",
            edges=(), edge_set_digest="empty-edge-set", index_schema_version=1,
            extractor_id="semantic-dependency-extractor/1",
            completeness_status=CompletenessStatus.NOT_CHECKED,
            reason="no independent reverse-lookup completeness evidence was supplied",
            evidence_id=None, discrepancies=(),
        )
        audit = audit_snapshot_incoming(result)
        artifact = ImpactedArtifact("contract-A", "caller_contract", "changed")
        plan = plan_impact("base", "candidate", "policy-v1", [artifact], [audit])
        self.assertEqual(plan.audit_statuses, (("contract-A", "NOT_CHECKED"),))
        self.assertEqual(plan.audit_bindings, (
            ("contract-A", "base", "contract-A", "scope", 1,
             "semantic-dependency-extractor/1", "", "empty-edge-set"),
        ))
        self.assertIn(ActionKind.FULL_REVALIDATION, {a.kind for a in plan.actions})

    def test_wrong_snapshot_binding_fails_closed(self):
        result = SnapshotIncomingResult(
            snapshot_root="stale-base", target_hash="contract-A", scope="scope",
            edges=(), edge_set_digest="digest", index_schema_version=1,
            extractor_id="semantic-dependency-extractor/1",
            completeness_status=CompletenessStatus.SUPPORTED_WITHIN_SCOPE,
            reason="claimed supported", evidence_id="audit-002", discrepancies=(),
        )
        audit = audit_snapshot_incoming(result)
        artifact = ImpactedArtifact("contract-A", "caller_contract", "changed")
        plan = plan_impact("base", "candidate", "policy-v1", [artifact], [audit])
        self.assertEqual(plan.audit_statuses, (("contract-A", "UNKNOWN"),))
        self.assertIn(ActionKind.FULL_REVALIDATION, {a.kind for a in plan.actions})

    def test_legacy_unbound_audit_is_not_accepted_by_default(self):
        artifact = ImpactedArtifact("contract-A", "caller_contract", "changed")
        audit = audit_dependency_completeness(
            "contract-A", set(), "scope",
            self.evidence("contract-A", set(), set(), "scope"),
        )
        plan = plan_impact("base", "candidate", "policy-v1", [artifact], [audit])
        self.assertEqual(plan.audit_statuses, (("contract-A", "NOT_CHECKED"),))
        self.assertIn(ActionKind.FULL_REVALIDATION, {a.kind for a in plan.actions})

    def test_reverse_lookup_binding_changes_plan_identity(self):
        artifact = ImpactedArtifact("contract-A", "caller_contract", "changed")
        def make_plan(evidence_id, edge_digest, schema_version=1,
                      extractor_id="semantic-dependency-extractor/1"):
            result = SnapshotIncomingResult(
                snapshot_root="base", target_hash="contract-A", scope="scope",
                edges=(), edge_set_digest=edge_digest, index_schema_version=schema_version,
                extractor_id=extractor_id,
                completeness_status=CompletenessStatus.SUPPORTED_WITHIN_SCOPE,
                reason="supported", evidence_id=evidence_id, discrepancies=(),
            )
            return plan_impact("base", "candidate", "policy-v1", [artifact],
                               [audit_snapshot_incoming(result)])
        self.assertNotEqual(make_plan("audit-A", "digest-A").plan_id,
                            make_plan("audit-B", "digest-A").plan_id)
        self.assertNotEqual(make_plan("audit-A", "digest-A").plan_id,
                            make_plan("audit-A", "digest-B").plan_id)
        self.assertNotEqual(make_plan("audit-A", "digest-A").plan_id,
                            make_plan("audit-A", "digest-A", schema_version=2).plan_id)
        self.assertNotEqual(make_plan("audit-A", "digest-A").plan_id,
                            make_plan("audit-A", "digest-A", extractor_id="other/2").plan_id)

    def test_every_discovered_call_site_requires_explicit_evidence_backed_decision(self):
        result = SnapshotIncomingResult(
            snapshot_root="base", target_hash="callee-v1", scope="all-static-call-sites",
            edges=(), edge_set_digest="edge-digest", index_schema_version=1,
            extractor_id="semantic-dependency-extractor/1",
            completeness_status=CompletenessStatus.SUPPORTED_WITHIN_SCOPE,
            reason="supported", evidence_id="audit", discrepancies=(),
        )
        from src.impact_planning import IncomingCallSite
        audit = audit_snapshot_incoming(result)
        audit = audit.__class__(**{**audit.__dict__, "incoming_call_sites": (
            IncomingCallSite("caller-A", "call:tax", "direct", "callee-v1"),
        )})
        artifact = ImpactedArtifact("callee-v1", "implementation", "callee changed")
        plan = plan_impact("base", "candidate", "policy", [artifact], [audit])
        self.assertIn(ActionKind.FULL_REVALIDATION, {a.kind for a in plan.actions})
        decision = CallSiteDecision(
            "caller-A", "call:tax", "direct", "callee-v1",
            CallSiteDisposition.MIGRATE, "callee-v2", "caller-A-v2",
            "caller contract requires new semantics", "compat-audit-001",
        )
        plan = plan_impact("base", "candidate", "policy", [artifact], [audit],
                           call_site_decisions=[decision])
        self.assertNotIn(ActionKind.FULL_REVALIDATION, {a.kind for a in plan.actions})
        self.assertIn(ActionKind.REWRITE_CALL_SITE, {a.kind for a in plan.actions})
        self.assertEqual(plan.call_site_decisions, (decision,))

    def test_preserve_requires_exact_old_hash_and_split_caller_versions_are_explicit(self):
        from src.impact_planning import IncomingCallSite
        result = SnapshotIncomingResult(
            snapshot_root="base", target_hash="shared-caller-v1", scope="all-static-call-sites",
            edges=(), edge_set_digest="edge-digest", index_schema_version=1,
            extractor_id="semantic-dependency-extractor/1",
            completeness_status=CompletenessStatus.SUPPORTED_WITHIN_SCOPE,
            reason="supported", evidence_id="audit", discrepancies=(),
        )
        audit = audit_snapshot_incoming(result)
        audit = audit.__class__(**{**audit.__dict__, "incoming_call_sites": (
            IncomingCallSite("consumer-old", "call:shared", "direct", "shared-caller-v1"),
            IncomingCallSite("consumer-new", "call:shared", "direct", "shared-caller-v1"),
        )})
        artifact = ImpactedArtifact("shared-caller-v1", "implementation", "callee contract split")
        decisions = [
            CallSiteDecision("consumer-old", "call:shared", "direct", "shared-caller-v1",
                CallSiteDisposition.PRESERVE, "shared-caller-v1", "consumer-old",
                "consumer contract requires legacy behavior", "compat-old"),
            CallSiteDecision("consumer-new", "call:shared", "direct", "shared-caller-v1",
                CallSiteDisposition.MIGRATE, "shared-caller-v2", "consumer-new-v2",
                "consumer contract accepts new behavior", "compat-new"),
        ]
        plan = plan_impact("base", "candidate", "policy", [artifact], [audit],
                           call_site_decisions=decisions)
        self.assertNotIn(ActionKind.FULL_REVALIDATION, {a.kind for a in plan.actions})
        self.assertEqual({d.selected_callee_hash for d in plan.call_site_decisions},
                         {"shared-caller-v1", "shared-caller-v2"})
        self.assertEqual(len(plan.call_site_decisions), 2)

    def test_mismatched_call_site_binding_and_missing_decision_evidence_are_rejected(self):
        from src.impact_planning import IncomingCallSite
        result = SnapshotIncomingResult(
            snapshot_root="base", target_hash="callee-v1", scope="scope", edges=(),
            edge_set_digest="digest", index_schema_version=1,
            extractor_id="semantic-dependency-extractor/1",
            completeness_status=CompletenessStatus.SUPPORTED_WITHIN_SCOPE,
            reason="supported", evidence_id="audit", discrepancies=(),
        )
        audit = audit_snapshot_incoming(result)
        audit = audit.__class__(**{**audit.__dict__, "incoming_call_sites": (
            IncomingCallSite("caller", "site", "target", "callee-v1"),
        )})
        artifact = ImpactedArtifact("callee-v1", "implementation", "changed")
        wrong = CallSiteDecision("caller", "site", "target", "other-callee",
            CallSiteDisposition.PRESERVE, "other-callee", "caller", "preserve", "evidence")
        with self.assertRaises(PlanningError):
            plan_impact("base", "candidate", "policy", [artifact], [audit],
                        call_site_decisions=[wrong])
        missing_evidence = CallSiteDecision("caller", "site", "target", "callee-v1",
            CallSiteDisposition.PRESERVE, "callee-v1", "caller", "preserve", None)
        with self.assertRaises(PlanningError):
            plan_impact("base", "candidate", "policy", [artifact], [audit],
                        call_site_decisions=[missing_evidence])

    def test_shared_caller_fork_decisions_are_bound_to_distinct_output_paths(self):
        from src.impact_planning import IncomingCallSite

        caller_hash = "shared-caller-v1"
        old_callee = "callee-v1"
        new_callee = "callee-v2"
        incoming = IncomingCallSite(
            caller_hash, "call:tax", "direct", old_callee,
        )
        audit = CompletenessAudit(
            status=CompletenessStatus.SUPPORTED_WITHIN_SCOPE,
            missing_dependencies=(), artifact_hash=old_callee,
            scope="all-static-call-sites", evidence_method="reverse-index",
            reason="supported within scope", snapshot_root="base",
            target_hash=old_callee, evidence_id="audit:shared",
            edge_set_digest="edge-digest", index_schema_version=1,
            extractor_id="extractor/1", incoming_call_sites=(incoming,),
        )
        outputs = (
            PlannedOutput(
                "shared-legacy", "shared-legacy", OutputOperation.ADD, None,
                "function", "content-digest-old", "preserve old consumer path",
                "evidence:legacy", caller_hash, "legacy-path",
            ),
            PlannedOutput(
                "shared-modern", "shared-modern", OutputOperation.ADD, None,
                "function", "content-digest-new", "fork modern consumer path",
                "evidence:modern", caller_hash, "modern-path",
            ),
        )
        decisions = (
            CallSiteDecision(
                caller_hash, "call:tax", "direct", old_callee,
                CallSiteDisposition.PRESERVE, old_callee, caller_hash,
                "legacy path remains on old callee", "evidence:legacy",
                "legacy-path", "shared-legacy",
            ),
            CallSiteDecision(
                caller_hash, "call:tax", "direct", old_callee,
                CallSiteDisposition.MIGRATE, new_callee, "shared-caller-v2",
                "modern path migrates to new callee", "evidence:modern",
                "modern-path", "shared-modern",
            ),
        )
        plan = plan_impact(
            "base", "candidate", "policy",
            [ImpactedArtifact(old_callee, "implementation", "callee update")],
            [audit], call_site_decisions=decisions, planned_outputs=outputs,
        )
        self.assertEqual(
            {decision.consumer_path_id for decision in plan.call_site_decisions},
            {"legacy-path", "modern-path"},
        )
        self.assertIn(ActionKind.REWRITE_CALL_SITE, {action.kind for action in plan.actions})

    def test_duplicate_audits_are_rejected(self):
        artifact = ImpactedArtifact("clause", "formal_clause", "changed")
        audit = audit_dependency_completeness("clause", set(), "scope", None)
        with self.assertRaises(PlanningError):
            plan_impact("base", "candidate", "policy-v1", [artifact], [audit, audit])


if __name__ == "__main__":
    unittest.main()
