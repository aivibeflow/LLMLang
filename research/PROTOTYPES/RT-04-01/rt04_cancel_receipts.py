"""Keep FFI result evidence tied to the invocation that owns reservations."""

from dataclasses import dataclass, replace
from typing import Literal

from rt04_backup_roles import BackupPair, permits


Policy = Literal["ack_by_invocation", "terminal_by_roles", "terminal_by_invocation"]
Kind = Literal["acknowledged", "not_found", "consumed", "retained", "unresolved"]
Phase = Literal["pending", "retained", "released"]


@dataclass(frozen=True)
class Invocation:
    roles: BackupPair
    generation: int


@dataclass(frozen=True)
class Evidence:
    subject: Invocation
    kind: Kind


@dataclass(frozen=True)
class Reservation:
    subject: Invocation
    phase: Phase = "pending"


def apply(policy: Policy, state: Reservation, evidence: Evidence) -> Reservation:
    """Update the wrapper record with one observation from the declared API."""
    if policy not in ("ack_by_invocation", "terminal_by_roles", "terminal_by_invocation"):
        raise ValueError("unsupported cancellation policy")
    if state.phase == "released":
        return state

    if policy == "terminal_by_roles":
        matches = state.subject.roles == evidence.subject.roles
    else:
        matches = state.subject == evidence.subject
    if not matches:
        return state

    if evidence.kind == "consumed" or (policy == "ack_by_invocation" and evidence.kind == "acknowledged"):
        return replace(state, phase="released")
    if evidence.kind == "retained":
        return replace(state, phase="retained")
    return state


def admits(state: Reservation, candidate: BackupPair) -> bool:
    """Use the bounded role footprint until consumption is established."""
    active = () if state.phase == "released" else (state.subject.roles,)
    return permits(active, candidate)
