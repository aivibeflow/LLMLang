import unittest

from policy import (
    Action,
    Approval,
    ApprovalLedger,
    Capability,
    Principal,
    PrincipalKind,
    Request,
    EvidenceContext,
    VerificationEvidence,
    authorize,
    verify_required_evidence,
)


HUMAN = Principal("reviewer-1", PrincipalKind.HUMAN)
AGENT = Principal("agent-7", PrincipalKind.AGENT)
OTHER_AGENT = Principal("agent-8", PrincipalKind.AGENT)


def request(action=Action.COMMIT, actor=AGENT, base="base-a", target="tree-a"):
    return Request(actor, action, "org/repository", base, target)


def capability(action=Action.COMMIT, actor=AGENT, repo="org/repository", snapshot="base-a"):
    return Capability(actor.subject, repo, frozenset({action}), snapshot)


def approval(for_request=None, approver=HUMAN, nonce="n-1", expires=500):
    return Approval(approver, (for_request or request()).binding, nonce, expires)


class AuthorizationTests(unittest.TestCase):
    def test_exact_request_with_capability_and_human_approval_is_allowed(self):
        result = authorize(request(), capability(), approval(), 100)
        self.assertTrue(result.allowed)
        self.assertEqual(result.nonce, "n-1")

    def test_missing_capability_is_denied(self):
        result = authorize(request(), None, approval(), 100)
        self.assertEqual(result.reason, "missing-capability")

    def test_capability_cannot_be_used_by_another_principal(self):
        result = authorize(request(actor=OTHER_AGENT), capability(), approval(), 100)
        self.assertEqual(result.reason, "wrong-principal")

    def test_capability_is_scoped_to_repository(self):
        result = authorize(request(), capability(repo="org/other"), approval(), 100)
        self.assertEqual(result.reason, "wrong-repository")

    def test_capability_is_scoped_to_base_snapshot(self):
        result = authorize(request(base="base-b"), capability(), approval(), 100)
        self.assertEqual(result.reason, "stale-snapshot")

    def test_grant_for_commit_does_not_authorize_push(self):
        result = authorize(request(action=Action.PUSH), capability(), approval(), 100)
        self.assertEqual(result.reason, "action-not-granted")

    def test_approval_is_bound_to_action_repository_base_and_target(self):
        result = authorize(
            request(target="tree-b"), capability(), approval(request()), 100
        )
        self.assertEqual(result.reason, "approval-binding-mismatch")

    def test_agent_cannot_issue_human_approval(self):
        result = authorize(
            request(), capability(), approval(approver=AGENT), 100
        )
        self.assertEqual(result.reason, "approver-is-not-human")

    def test_expired_approval_is_denied(self):
        result = authorize(request(), capability(), approval(expires=100), 100)
        self.assertEqual(result.reason, "approval-expired")

    def test_consumed_approval_cannot_be_replayed(self):
        result = authorize(request(), capability(), approval(), 100, {"n-1"})
        self.assertEqual(result.reason, "approval-replayed")

    def test_validation_does_not_require_approval(self):
        validation = request(action=Action.VALIDATE)
        result = authorize(
            validation,
            capability(action=Action.VALIDATE),
            None,
            100,
        )
        self.assertTrue(result.allowed)
        self.assertIsNone(result.nonce)

    def test_ledger_reserves_and_consumes_nonce_once(self):
        decision = authorize(request(), capability(), approval(), 100)
        ledger = ApprovalLedger()
        self.assertTrue(ledger.reserve(decision))
        self.assertFalse(ledger.reserve(decision))
        self.assertTrue(ledger.complete("n-1"))
        self.assertFalse(ledger.reserve(decision))
        self.assertFalse(ledger.complete("n-1"))

    def test_failed_operation_can_release_a_reservation(self):
        decision = authorize(request(), capability(), approval(), 100)
        ledger = ApprovalLedger()
        self.assertTrue(ledger.reserve(decision))
        self.assertTrue(ledger.release("n-1"))
        self.assertTrue(ledger.reserve(decision))


class VerificationEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.context = EvidenceContext("candidate-a", "toolchain-a", "target-a", "assumptions-a")
        self.required = {"unit-tests", "proof-check"}
        self.trusted = {"verifier-ci"}
        self.evidence = [
            VerificationEvidence("unit-tests", self.context, "verifier-ci", "passed"),
            VerificationEvidence("proof-check", self.context, "verifier-ci", "passed"),
        ]

    def check(self, evidence=None, context=None):
        return verify_required_evidence(
            self.required,
            context or self.context,
            evidence if evidence is not None else self.evidence,
            self.trusted,
        )

    def test_complete_current_evidence_from_trusted_verifier_is_allowed(self):
        self.assertTrue(self.check().allowed)

    def test_missing_required_check_is_denied(self):
        self.assertEqual(self.check(self.evidence[:1]).reason, "required-evidence-missing")

    def test_changed_candidate_invalidates_evidence(self):
        changed = EvidenceContext("candidate-b", "toolchain-a", "target-a", "assumptions-a")
        self.assertEqual(self.check(context=changed).reason, "stale-evidence")

    def test_changed_toolchain_invalidates_evidence(self):
        changed = EvidenceContext("candidate-a", "toolchain-b", "target-a", "assumptions-a")
        self.assertEqual(self.check(context=changed).reason, "stale-evidence")

    def test_changed_target_invalidates_evidence(self):
        changed = EvidenceContext("candidate-a", "toolchain-a", "target-b", "assumptions-a")
        self.assertEqual(self.check(context=changed).reason, "stale-evidence")

    def test_changed_assumptions_invalidates_evidence(self):
        changed = EvidenceContext("candidate-a", "toolchain-a", "target-a", "assumptions-b")
        self.assertEqual(self.check(context=changed).reason, "stale-evidence")

    def test_untrusted_verifier_cannot_satisfy_a_gate(self):
        evidence = [
            VerificationEvidence("unit-tests", self.context, "agent", "passed"),
            self.evidence[1],
        ]
        self.assertEqual(self.check(evidence).reason, "untrusted-verifier")

    def test_failed_check_is_denied(self):
        evidence = [
            VerificationEvidence("unit-tests", self.context, "verifier-ci", "failed"),
            self.evidence[1],
        ]
        self.assertEqual(self.check(evidence).reason, "check-not-passed")

    def test_unknown_check_result_is_denied(self):
        evidence = [
            VerificationEvidence("unit-tests", self.context, "verifier-ci", "unknown"),
            self.evidence[1],
        ]
        self.assertEqual(self.check(evidence).reason, "check-not-passed")

    def test_duplicate_check_records_are_denied(self):
        self.assertEqual(self.check(self.evidence + [self.evidence[0]]).reason,
                         "duplicate-check-evidence")

    def test_evidence_digest_commits_to_verifier_and_result(self):
        original = self.evidence[0]
        forged = VerificationEvidence(original.check_id, original.context, "agent", "passed")
        failed = VerificationEvidence(original.check_id, original.context, original.verifier, "failed")
        self.assertNotEqual(original.digest(), forged.digest())
        self.assertNotEqual(original.digest(), failed.digest())


if __name__ == "__main__":
    unittest.main()
