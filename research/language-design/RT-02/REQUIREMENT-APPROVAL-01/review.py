"""Finite model of exact human review binding. Authentication is supplied by the caller."""

from dataclasses import asdict, dataclass
from enum import StrEnum

from src.semantic_graph import digest


class Decision(StrEnum):
    ACCEPT = "ACCEPT"
    REVISE = "REVISE"
    CLARIFY = "CLARIFY"
    REJECT = "REJECT"


class FormalStatus(StrEnum):
    PASSED_REQUIRED_CHECKS = "passed-required-checks"
    REFUTED = "refuted"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class ReviewPackage:
    semantic: str
    formal_model: str
    intent_sources: str
    provenance: str
    reconstruction: str
    scenarios: str
    analysis: str
    assumptions: str
    formal_status: FormalStatus
    unresolved_business_questions: tuple[str, ...] = ()
    missing_provenance: tuple[str, ...] = ()
    unsupported_clauses: tuple[str, ...] = ()

    @property
    def identity(self):
        return digest({"type": "rt02-review-package-v1", **asdict(self)})


@dataclass(frozen=True)
class ReviewSubject:
    project: str
    slot: str
    round: str
    policy: str
    package: ReviewPackage

    @property
    def identity(self):
        return digest({
            "type": "rt02-review-subject-v1",
            "project": self.project,
            "slot": self.slot,
            "round": self.round,
            "policy": self.policy,
            "semantic": self.package.semantic,
            "package": self.package.identity,
        })


@dataclass(frozen=True)
class Grant:
    actor: str
    project: str
    slot: str
    policy: str
    revision: str

    def permits(self, actor, subject):
        return ((self.actor, self.project, self.slot, self.policy)
                == (actor, subject.project, subject.slot, subject.policy))


@dataclass(frozen=True)
class ReviewAction:
    subject: str
    actor: str
    grant_revision: str
    decision: Decision
    rationale: str

    @property
    def identity(self):
        return digest({"type": "rt02-review-action-v1", **asdict(self)})


FOLLOW_UP = {
    Decision.REVISE: "revision-requested",
    Decision.CLARIFY: "clarification-requested",
    Decision.REJECT: "candidate-rejected",
}


FORMAL_GATE = {
    FormalStatus.PASSED_REQUIRED_CHECKS: "eligible-for-contract-admission",
    FormalStatus.REFUTED: "formal-refuted",
    FormalStatus.UNKNOWN: "formal-unknown",
    FormalStatus.UNSUPPORTED: "formal-unsupported",
}


def assess(current, action, *, authenticated_actor, active_grants):
    """Return intent review and formal-contract applicability as separate outcomes."""
    if authenticated_actor != action.actor:
        return "unauthenticated-reviewer", "blocked"
    if current.identity != action.subject:
        return "different-review-subject", "blocked"
    grant = active_grants.get(action.grant_revision)
    if grant is None or grant.revision != action.grant_revision or not grant.permits(action.actor, current):
        return "out-of-scope-authority", "blocked"
    if not isinstance(action.decision, Decision) or not action.rationale.strip():
        return "invalid-review-action", "blocked"
    if action.decision != Decision.ACCEPT:
        return FOLLOW_UP[action.decision], "blocked"
    package = current.package
    if package.unresolved_business_questions or package.missing_provenance or package.unsupported_clauses:
        return "incomplete-review-package", "blocked"
    return "intent-accepted", FORMAL_GATE[package.formal_status]
