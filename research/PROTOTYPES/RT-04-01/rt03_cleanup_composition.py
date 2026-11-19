"""Finite outcome algebra for Scenario 97 cleanup composition.

The model separates primary outcome identity, cleanup-failure composition,
cleanup trace, and resource ownership/disposition. It is a discriminator model,
not LLMLang semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Policy = Literal["P", "A", "N", "R", "D", "X"]
PrimaryKind = Literal["return", "domain_error", "cancellation", "fuel", "panic"]
CleanupResult = Literal["ok", "error", "panic"]
Disposition = Literal["released", "retained", "consumed", "indeterminate"]
TransferTiming = Literal["transfer_first", "stage_until_cleanup"]


@dataclass(frozen=True)
class CleanupAction:
    resource: str
    result: CleanupResult
    disposition: Disposition


@dataclass(frozen=True)
class CleanupObservation:
    resource: str
    attempted: bool
    result: CleanupResult | None
    disposition: Disposition | None


@dataclass(frozen=True)
class Observation:
    policy: Policy
    primary_kind: PrimaryKind
    primary_payload: str
    terminal_kind: str
    terminal_payload: str
    suppressed_causes: tuple[str, ...]
    aggregate_causes: tuple[str, ...]
    nested_cleanup_causes: tuple[str, ...]
    replaced_primary: str | None
    fatal_causes: tuple[str, ...]
    cleanup_trace: tuple[CleanupObservation, ...]
    owners: tuple[tuple[str, str], ...]
    resource_states: tuple[tuple[str, str], ...]
    effects: tuple[str, ...]
    owned_value: bool
    transfer_timing: TransferTiming


_POLICIES = {"P", "A", "N", "R", "D", "X"}
_PRIMARY_KINDS = {"return", "domain_error", "cancellation", "fuel", "panic"}
_DISPOSITIONS = {"released", "retained", "consumed", "indeterminate"}


def compose_cleanup_outcome(
    primary_kind: PrimaryKind,
    primary_payload: str,
    actions: tuple[CleanupAction, ...],
    *,
    policy: Policy,
    cleanup_budget: int,
    owned_value: bool = False,
    transfer_timing: TransferTiming = "transfer_first",
    effects: tuple[str, ...] = (),
) -> Observation:
    """Execute a fixed cleanup plan and project it through one candidate policy.

    Actions are already in execution order (innermost first). A finite budget
    permits that many attempts; later actions are recorded as blocked. API
    disposition is explicit because an error does not imply whether a resource
    was retained, consumed, or left indeterminate.
    """
    if primary_kind not in _PRIMARY_KINDS or not isinstance(primary_payload, str):
        raise ValueError("unsupported primary outcome")
    if policy not in _POLICIES:
        raise ValueError("unsupported composition policy")
    if type(cleanup_budget) is not int or cleanup_budget < 0:
        raise ValueError("cleanup_budget must be a non-negative integer")
    if type(owned_value) is not bool:
        raise ValueError("owned_value must be boolean")
    if transfer_timing not in {"transfer_first", "stage_until_cleanup"}:
        raise ValueError("unsupported transfer timing")
    if not isinstance(actions, tuple) or any(not isinstance(a, CleanupAction) for a in actions):
        raise ValueError("actions must be a tuple of CleanupAction values")
    names = tuple(a.resource for a in actions)
    if any(not isinstance(n, str) or not n for n in names) or len(set(names)) != len(names):
        raise ValueError("cleanup resources must be unique non-empty names")
    if any(a.result not in {"ok", "error", "panic"} or a.disposition not in _DISPOSITIONS for a in actions):
        raise ValueError("unsupported cleanup result or resource disposition")
    if any(a.result == "ok" and a.disposition != "released" for a in actions):
        raise ValueError("successful cleanup must report released disposition")
    if not isinstance(effects, tuple) or any(not isinstance(e, str) for e in effects):
        raise ValueError("effects must be a tuple of strings")

    owners = {name: "callee" for name in names}
    states = {name: "live" for name in names}
    if owned_value:
        if transfer_timing == "transfer_first":
            owners["returned_value"] = "caller"
            states["returned_value"] = "caller_owned"
        else:
            owners["returned_value"] = "pending_return"
            states["returned_value"] = "pending"

    trace: list[CleanupObservation] = []
    failures: list[str] = []
    fatals: list[str] = []
    attempted = 0
    for action in actions:
        if attempted >= cleanup_budget:
            trace.append(CleanupObservation(action.resource, False, None, None))
            owners[action.resource] = "callee_cleanup_debt"
            states[action.resource] = "cleanup_blocked"
            continue
        attempted += 1
        trace.append(CleanupObservation(action.resource, True, action.result, action.disposition))
        if action.result == "ok":
            owners.pop(action.resource, None)
            states[action.resource] = "released"
            continue
        cause = f"cleanup:{action.resource}:{action.result}"
        failures.append(cause)
        if action.result == "panic":
            fatals.append(cause)
        if action.disposition == "retained":
            owners[action.resource] = "callee_cleanup_debt"
            states[action.resource] = "retained_after_error"
        elif action.disposition == "consumed":
            owners.pop(action.resource, None)
            states[action.resource] = "consumed_with_error"
        else:
            owners[action.resource] = "indeterminate_cleanup_debt"
            states[action.resource] = "indeterminate_after_error"

    if owned_value and transfer_timing == "stage_until_cleanup":
        cleanup_complete = all(item.attempted and item.result == "ok" for item in trace)
        if cleanup_complete:
            owners["returned_value"] = "caller"
            states["returned_value"] = "caller_owned"
        else:
            owners["returned_value"] = "pending_return_cleanup_debt"
            states["returned_value"] = "pending_with_cleanup_debt"

    primary = f"{primary_kind}:{primary_payload}"
    terminal_kind, terminal_payload = primary_kind, primary_payload
    suppressed: tuple[str, ...] = ()
    aggregate: tuple[str, ...] = ()
    nested: tuple[str, ...] = ()
    replaced: str | None = None

    if policy == "P":
        suppressed = tuple(failures)
    elif policy == "A":
        aggregate = (primary, *failures) if failures else (primary,)
    elif policy == "N":
        nested = tuple(failures)
    elif policy == "R" and failures:
        terminal_kind, terminal_payload = "cleanup_error", failures[-1]
        replaced = primary
    elif policy == "D":
        pass
    elif policy == "X" and fatals and primary_kind == "panic":
        terminal_kind, terminal_payload = "abort", fatals[-1]
        suppressed = tuple(f for f in failures if f not in fatals)
    elif policy == "X" and fatals:
        terminal_kind, terminal_payload = "panic", fatals[-1]
        replaced = primary
        suppressed = tuple(f for f in failures if f not in fatals)
    elif policy == "X":
        suppressed = tuple(failures)

    return Observation(
        policy, primary_kind, primary_payload, terminal_kind, terminal_payload,
        suppressed, aggregate, nested, replaced, tuple(fatals), tuple(trace),
        tuple(sorted(owners.items())), tuple(sorted(states.items())), effects,
        owned_value, transfer_timing,
    )
