import unittest
from dataclasses import replace

from src.semantic_dependency_index import SnapshotIncomingResult

from src.impact_planning import (
    ActionKind, CallSiteDecision, CallSiteDisposition, CompletenessEvidence,
    CompletenessStatus, CompletenessAudit, IncomingCallSite, ImpactedArtifact,
    OutputOperation, PlannedOutput, NonInterferenceCertificate, PlanningError, audit_dependency_completeness,
    audit_snapshot_incoming, compute_planned_action_id, dependency_digest,
    no_action_is_justified, plan_impact, PlannedAction, validate_planned_action_dag,
    validate_action_kind_policy, ACTION_KIND_POLICY_VERSION,
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
            IncomingCallSite("caller-A", "call:tax", "direct", "callee-v1", required_contract_hash="req-contract-v1", provided_contract_hash="provided-contract-v1"),
        )})
        artifact = ImpactedArtifact("callee-v1", "implementation", "callee changed")
        plan = plan_impact("base", "candidate", "policy", [artifact], [audit])
        self.assertIn(ActionKind.FULL_REVALIDATION, {a.kind for a in plan.actions})
        decision = CallSiteDecision(
            "caller-A", "call:tax", "direct", "callee-v1",
            CallSiteDisposition.MIGRATE, "callee-v2", "caller-A-v2",
            "caller contract requires new semantics", "compat-audit-001",
            "req-contract-v1", "provided-contract-v1", "provided-contract-v2", "PROVEN",
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
            IncomingCallSite("consumer-old", "call:shared", "direct", "shared-caller-v1", required_contract_hash="req-old", provided_contract_hash="provided-old"),
            IncomingCallSite("consumer-new", "call:shared", "direct", "shared-caller-v1", required_contract_hash="req-new", provided_contract_hash="provided-old"),
        )})
        artifact = ImpactedArtifact("shared-caller-v1", "implementation", "callee contract split")
        decisions = [
            CallSiteDecision("consumer-old", "call:shared", "direct", "shared-caller-v1",
                CallSiteDisposition.PRESERVE, "shared-caller-v1", "consumer-old",
                "consumer contract requires legacy behavior", "compat-old",
                "req-old", "provided-old", "provided-old", "PROVEN"),
            CallSiteDecision("consumer-new", "call:shared", "direct", "shared-caller-v1",
                CallSiteDisposition.MIGRATE, "shared-caller-v2", "consumer-new-v2",
                "consumer contract accepts new behavior", "compat-new",
                "req-new", "provided-old", "provided-new", "PROVEN"),
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
            IncomingCallSite("caller", "site", "target", "callee-v1", required_contract_hash="req-contract", provided_contract_hash="provided-contract"),
        )})
        artifact = ImpactedArtifact("callee-v1", "implementation", "changed")
        wrong = CallSiteDecision("caller", "site", "target", "other-callee",
            CallSiteDisposition.PRESERVE, "other-callee", "caller", "preserve", "evidence",
            "req-contract", "provided-contract", "provided-contract", "PROVEN")
        with self.assertRaises(PlanningError):
            plan_impact("base", "candidate", "policy", [artifact], [audit],
                        call_site_decisions=[wrong])
        missing_evidence = CallSiteDecision("caller", "site", "target", "callee-v1",
            CallSiteDisposition.PRESERVE, "callee-v1", "caller", "preserve", None,
            "req-contract", "provided-contract", "provided-contract", "PROVEN")
        with self.assertRaises(PlanningError):
            plan_impact("base", "candidate", "policy", [artifact], [audit],
                        call_site_decisions=[missing_evidence])

    def test_decision_must_keep_contract_binding_and_proven_compatibility(self):
        from src.impact_planning import IncomingCallSite
        result = SnapshotIncomingResult(
            snapshot_root="base", target_hash="callee-v1", scope="scope", edges=(),
            edge_set_digest="digest", index_schema_version=2,
            extractor_id="semantic-dependency-extractor/2",
            completeness_status=CompletenessStatus.SUPPORTED_WITHIN_SCOPE,
            reason="supported", evidence_id="audit", discrepancies=(),
        )
        audit = audit_snapshot_incoming(result)
        audit = audit.__class__(**{**audit.__dict__, "incoming_call_sites": (
            IncomingCallSite("caller", "site", "target", "callee-v1",
                required_contract_hash="required-v1", provided_contract_hash="provided-v1"),
        )})
        artifact = ImpactedArtifact("callee-v1", "implementation", "changed")

        wrong_requirement = CallSiteDecision(
            "caller", "site", "target", "callee-v1", CallSiteDisposition.MIGRATE,
            "callee-v2", "caller-v2", "migrate", "evidence",
            "required-v2", "provided-v1", "provided-v2", "PROVEN")
        with self.assertRaises(PlanningError):
            plan_impact("base", "candidate", "policy", [artifact], [audit],
                        call_site_decisions=[wrong_requirement])

        unproven = CallSiteDecision(
            "caller", "site", "target", "callee-v1", CallSiteDisposition.MIGRATE,
            "callee-v2", "caller-v2", "migrate", "evidence",
            "required-v1", "provided-v1", "provided-v2", "UNKNOWN")
        with self.assertRaises(PlanningError):
            plan_impact("base", "candidate", "policy", [artifact], [audit],
                        call_site_decisions=[unproven])

        preserve_changed_contract = CallSiteDecision(
            "caller", "site", "target", "callee-v1", CallSiteDisposition.PRESERVE,
            "callee-v1", "caller", "preserve", "evidence",
            "required-v1", "provided-v1", "provided-v2", "PROVEN")
        with self.assertRaises(PlanningError):
            plan_impact("base", "candidate", "policy", [artifact], [audit],
                        call_site_decisions=[preserve_changed_contract])

    def test_shared_caller_fork_outputs_are_bound_per_consumer_path(self):
        caller_hash = "shared-caller-v1"
        old_callee = "callee-v1"
        new_callee = "callee-v2"
        audit = CompletenessAudit(
            status=CompletenessStatus.SUPPORTED_WITHIN_SCOPE,
            missing_dependencies=(), artifact_hash=old_callee,
            scope="all-static-call-sites", evidence_method="snapshot-reverse-lookup",
            reason="supported within declared scope", snapshot_root="base",
            target_hash=old_callee, evidence_id="audit:shared",
            edge_set_digest="edge-digest", index_schema_version=2,
            extractor_id="extractor/v2",
            incoming_call_sites=(IncomingCallSite(
                caller_hash, "call:tax", "direct", old_callee,
                required_contract_hash="required-contract",
                provided_contract_hash="provided-old",
            ),),
        )
        outputs = (
            PlannedOutput(
                "callee-v2", "callee", OutputOperation.REPLACE, old_callee,
                "function", "payload-digest-callee", "migrate callee",
                "evidence:callee",
            ),
            PlannedOutput(
                "shared-legacy", "shared-legacy", OutputOperation.ADD, None,
                "function", "payload-digest-legacy", "preserve legacy path",
                "evidence:legacy", caller_hash, "legacy-path",
            ),
            PlannedOutput(
                "shared-modern", "shared-modern", OutputOperation.ADD, None,
                "function", "payload-digest-modern", "fork modern path",
                "evidence:modern", caller_hash, "modern-path",
            ),
        )
        decisions = (
            CallSiteDecision(
                caller_hash, "call:tax", "direct", old_callee,
                CallSiteDisposition.PRESERVE, old_callee, caller_hash,
                "legacy consumer keeps exact callee", "evidence:legacy",
                "required-contract", "provided-old", "provided-old", "PROVEN",
                None, "legacy-path", "shared-legacy", None,
            ),
            CallSiteDecision(
                caller_hash, "call:tax", "direct", old_callee,
                CallSiteDisposition.MIGRATE, None, None,
                "modern consumer receives new callee and caller fork", "evidence:modern",
                "required-contract", "provided-old", "provided-new", "PROVEN",
                None, "modern-path", "shared-modern", "callee-v2",
            ),
        )
        plan = plan_impact(
            "base", "candidate", "policy",
            [ImpactedArtifact(old_callee, "implementation", "callee change")],
            [audit], call_site_decisions=decisions, planned_outputs=outputs,
        )
        self.assertEqual(
            {item.consumer_path_id for item in plan.call_site_decisions},
            {"legacy-path", "modern-path"},
        )
        self.assertEqual(
            {item.resulting_output_id for item in plan.call_site_decisions},
            {"shared-legacy", "shared-modern"},
        )
        self.assertIn(ActionKind.REWRITE_CALL_SITE, {item.kind for item in plan.actions})

    def test_duplicate_audits_are_rejected(self):
        artifact = ImpactedArtifact("clause", "formal_clause", "changed")
        audit = audit_dependency_completeness("clause", set(), "scope", None)
        with self.assertRaises(PlanningError):
            plan_impact("base", "candidate", "policy-v1", [artifact], [audit, audit])


    def test_planned_action_ids_are_deterministic_and_content_sensitive(self):
        action = PlannedAction(ActionKind.REBUILD, "impl-A", "rebuild changed implementation")
        identified = replace(action, action_id=compute_planned_action_id(action))
        self.assertEqual(identified.action_id, compute_planned_action_id(action))
        changed = replace(action, reason="different rationale")
        self.assertNotEqual(identified.action_id, compute_planned_action_id(changed))
        validate_planned_action_dag((identified,))

    def test_action_dag_accepts_prerequisite_order_independently_of_tuple_order(self):
        first = PlannedAction(ActionKind.RE_DERIVE, "model-A", "derive")
        first = replace(first, action_id=compute_planned_action_id(first))
        second = PlannedAction(
            ActionKind.REBUILD, "impl-A", "build",
            prerequisite_action_ids=(first.action_id,),
        )
        second = replace(second, action_id=compute_planned_action_id(second))
        validate_planned_action_dag((second, first))
        self.assertEqual(len({first.action_id, second.action_id}), 2)

    def test_action_dag_rejects_duplicate_action_ids(self):
        first = PlannedAction(ActionKind.RE_DERIVE, "model-A", "derive")
        first = replace(first, action_id=compute_planned_action_id(first))
        with self.assertRaisesRegex(PlanningError, "unique"):
            validate_planned_action_dag((first, first))

    def test_action_dag_rejects_unknown_prerequisite(self):
        action = PlannedAction(
            ActionKind.REBUILD, "impl-A", "build",
            action_id="action-build", prerequisite_action_ids=("missing-action",),
        )
        with self.assertRaisesRegex(PlanningError, "unknown prerequisite"):
            validate_planned_action_dag((action,))

    def test_action_dag_rejects_self_and_multi_node_cycles(self):
        self_cycle = PlannedAction(
            ActionKind.REBUILD, "impl-A", "build",
            action_id="self", prerequisite_action_ids=("self",),
        )
        with self.assertRaisesRegex(PlanningError, "depend on itself"):
            validate_planned_action_dag((self_cycle,))

        first = PlannedAction(
            ActionKind.RE_DERIVE, "model-A", "derive",
            action_id="first", prerequisite_action_ids=("second",),
        )
        second = PlannedAction(
            ActionKind.REBUILD, "impl-A", "build",
            action_id="second", prerequisite_action_ids=("first",),
        )
        with self.assertRaisesRegex(PlanningError, "contains a cycle"):
            validate_planned_action_dag((first, second))

    def test_plan_generation_assigns_action_ids_and_binds_them_into_plan_identity(self):
        artifact = ImpactedArtifact("impl-A", "implementation", "changed")
        audit = audit_dependency_completeness(
            "impl-A", set(), "scope",
            self.evidence("impl-A", set(), set(), "scope"),
        )
        first = plan_impact(
            "base", "candidate", "policy-v1", [artifact], [audit],
            require_snapshot_evidence=False,
        )
        second = plan_impact(
            "base", "candidate", "policy-v1", [artifact], [audit],
            require_snapshot_evidence=False,
        )
        self.assertTrue(first.actions)
        self.assertTrue(all(action.action_id for action in first.actions))
        self.assertEqual(first.plan_id, second.plan_id)
        self.assertNotEqual(
            first.plan_id,
            plan_impact(
                "base", "candidate", "policy-v2", [artifact], [audit],
                require_snapshot_evidence=False,
            ).plan_id,
        )
        validate_planned_action_dag(first.actions)


    def test_action_kind_policy_accepts_only_declared_subject_action_pairs(self):
        accepted = (
            PlannedAction(ActionKind.RE_DERIVE, "clause", "derive", subject_kind="formal_clause"),
            PlannedAction(ActionKind.REGENERATE_TESTS, "tests", "generate", subject_kind="test_suite"),
            PlannedAction(ActionKind.RUN_TESTS, "tests", "run", subject_kind="test_suite"),
            PlannedAction(ActionKind.REBUILD, "impl", "build", subject_kind="implementation"),
            PlannedAction(ActionKind.RUN_TESTS, "impl", "test candidate", subject_kind="implementation"),
            PlannedAction(ActionKind.REPROVE, "proof", "prove", subject_kind="proof"),
            PlannedAction(ActionKind.HUMAN_REVIEW, "req", "review", subject_kind="requirement"),
            PlannedAction(ActionKind.REWRITE_CALL_SITE, "caller", "rewrite", subject_kind="call_site"),
            PlannedAction(ActionKind.FULL_REVALIDATION, "candidate", "fallback", subject_kind="candidate"),
        )
        validate_action_kind_policy(accepted)
        self.assertEqual(ACTION_KIND_POLICY_VERSION, "cip-action-policy/1")

    def test_action_kind_policy_rejects_mismatched_and_unknown_subjects(self):
        with self.assertRaisesRegex(PlanningError, "not permitted"):
            validate_action_kind_policy((
                PlannedAction(ActionKind.REPROVE, "impl", "wrong action", subject_kind="implementation"),
            ))
        with self.assertRaisesRegex(PlanningError, "unsupported"):
            validate_action_kind_policy((
                PlannedAction(ActionKind.REBUILD, "opaque", "unknown", subject_kind="opaque_kind"),
            ))
        with self.assertRaisesRegex(PlanningError, "unsupported"):
            validate_action_kind_policy((
                PlannedAction(ActionKind.REBUILD, "opaque", "missing subject kind"),
            ))

    def test_action_subject_kind_changes_action_and_plan_identity(self):
        plain = PlannedAction(ActionKind.REBUILD, "impl", "build", subject_kind="implementation")
        other = replace(plain, subject_kind="generated_artifact")
        self.assertNotEqual(compute_planned_action_id(plain), compute_planned_action_id(other))


if __name__ == "__main__":
    unittest.main()
