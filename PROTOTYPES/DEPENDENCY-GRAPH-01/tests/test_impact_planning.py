import unittest

from src.impact_planning import (
    ActionKind, CompletenessEvidence, CompletenessStatus, ImpactedArtifact,
    NonInterferenceCertificate, PlanningError, audit_dependency_completeness,
    dependency_digest, no_action_is_justified, plan_impact,
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
        plan = plan_impact("base", "candidate", "policy-v1", [artifact], [audit])
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
        plan = plan_impact("base", "candidate", "policy-v1", [artifact], [audit])
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
        plan = plan_impact("base", "candidate", "policy-v1", artifacts, audits)
        kinds = {action.kind for action in plan.actions}
        self.assertTrue({ActionKind.REGENERATE_TESTS, ActionKind.RUN_TESTS,
                         ActionKind.REPROVE, ActionKind.REBUILD}.issubset(kinds))
        self.assertNotIn(ActionKind.FULL_REVALIDATION, kinds)

    def test_unknown_artifact_kind_forces_conservative_actions(self):
        artifact = ImpactedArtifact("opaque", "unclassified_kind", "changed")
        audit = audit_dependency_completeness(
            "opaque", set(), "scope", self.evidence("opaque", set(), set(), "scope"))
        plan = plan_impact("base", "candidate", "policy-v1", [artifact], [audit])
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
        first = plan_impact("base", "candidate", "policy-v1", [artifact], [audit])
        second = plan_impact("base", "candidate", "policy-v1", [artifact], [audit])
        other_policy = plan_impact("base", "candidate", "policy-v2", [artifact], [audit])
        self.assertEqual(first.plan_id, second.plan_id)
        self.assertNotEqual(first.plan_id, other_policy.plan_id)

    def test_duplicate_audits_are_rejected(self):
        artifact = ImpactedArtifact("clause", "formal_clause", "changed")
        audit = audit_dependency_completeness("clause", set(), "scope", None)
        with self.assertRaises(PlanningError):
            plan_impact("base", "candidate", "policy-v1", [artifact], [audit, audit])


if __name__ == "__main__":
    unittest.main()
