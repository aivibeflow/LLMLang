"""Small executable authorization model for RT-16 boundary cases."""

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Optional


class Action(str, Enum):
    READ = "read"
    PROPOSE = "propose"
    VALIDATE = "validate"
    ACCEPT = "accept"
    COMMIT = "commit"
    PUSH = "push"
    PUBLISH = "publish"
    DELETE = "delete"


class PrincipalKind(str, Enum):
    HUMAN = "human"
    AGENT = "agent"
    SERVICE = "service"


HUMAN_APPROVAL_ACTIONS = {
    Action.ACCEPT,
    Action.COMMIT,
    Action.PUSH,
    Action.PUBLISH,
    Action.DELETE,
}


@dataclass(frozen=True)
class Principal:
    subject: str
    kind: PrincipalKind


@dataclass(frozen=True)
class Capability:
    subject: str
    repository: str
    actions: frozenset
    snapshot: Optional[str] = None


@dataclass(frozen=True)
class Request:
    actor: Principal
    action: Action
    repository: str
    base_revision: str
    target: str

    @property
    def binding(self):
        return (
            self.action.value,
            self.repository,
            self.base_revision,
            self.target,
        )


@dataclass(frozen=True)
class Approval:
    approver: Principal
    binding: tuple
    nonce: str
    expires_at: int


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    nonce: Optional[str] = None


def authorize(request, capability, approval, now, used_nonces=frozenset()):
    if capability is None:
        return Decision(False, "missing-capability")
    if capability.subject != request.actor.subject:
        return Decision(False, "wrong-principal")
    if capability.repository != request.repository:
        return Decision(False, "wrong-repository")
    if capability.snapshot is not None and capability.snapshot != request.base_revision:
        return Decision(False, "stale-snapshot")
    if request.action not in capability.actions:
        return Decision(False, "action-not-granted")

    if request.action in HUMAN_APPROVAL_ACTIONS:
        if approval is None:
            return Decision(False, "approval-required")
        if approval.approver.kind is not PrincipalKind.HUMAN:
            return Decision(False, "approver-is-not-human")
        if approval.binding != request.binding:
            return Decision(False, "approval-binding-mismatch")
        if approval.expires_at <= now:
            return Decision(False, "approval-expired")
        if approval.nonce in used_nonces:
            return Decision(False, "approval-replayed")
        return Decision(True, "authorized", approval.nonce)

    return Decision(True, "authorized")


class ApprovalLedger:
    """Reserve approval nonces before execution and consume them at completion."""

    def __init__(self):
        self._reserved = set()
        self._consumed = set()

    @property
    def used(self):
        return frozenset(self._reserved | self._consumed)

    def reserve(self, decision):
        if not decision.allowed or decision.nonce is None:
            return False
        if decision.nonce in self.used:
            return False
        self._reserved.add(decision.nonce)
        return True

    def complete(self, nonce):
        if nonce not in self._reserved:
            return False
        self._reserved.remove(nonce)
        self._consumed.add(nonce)
        return True

    def release(self, nonce):
        if nonce not in self._reserved:
            return False
        self._reserved.remove(nonce)
        return True


@dataclass(frozen=True)
class EvidenceContext:
    candidate: str
    toolchain: str
    target: str
    assumptions: str

    def canonical_value(self):
        return {
            "assumptions": self.assumptions,
            "candidate": self.candidate,
            "target": self.target,
            "toolchain": self.toolchain,
        }


@dataclass(frozen=True)
class VerificationEvidence:
    check_id: str
    context: EvidenceContext
    verifier: str
    result: str

    def digest(self):
        payload = {
            "check_id": self.check_id,
            "context": self.context.canonical_value(),
            "result": self.result,
            "verifier": self.verifier,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EvidenceDecision:
    allowed: bool
    reason: str


def verify_required_evidence(required_checks, expected_context, evidence, trusted_verifiers):
    seen = set()
    passed = set()
    for item in evidence:
        if item.check_id in seen:
            return EvidenceDecision(False, "duplicate-check-evidence")
        seen.add(item.check_id)
        if item.check_id not in required_checks:
            continue
        if item.context != expected_context:
            return EvidenceDecision(False, "stale-evidence")
        if item.verifier not in trusted_verifiers:
            return EvidenceDecision(False, "untrusted-verifier")
        if item.result != "passed":
            return EvidenceDecision(False, "check-not-passed")
        passed.add(item.check_id)

    if passed != set(required_checks):
        return EvidenceDecision(False, "required-evidence-missing")
    return EvidenceDecision(True, "required-evidence-current")
