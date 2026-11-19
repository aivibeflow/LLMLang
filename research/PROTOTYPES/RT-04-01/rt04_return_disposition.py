"""Small COR-13 call-boundary model with explicit cleanup disposition."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Disposition = Literal["ok", "retained_error", "consumed_error", "indeterminate"]
BodyOutcome = Literal["success", "domain_error_before_transfer", "domain_error_after_transfer"]
TransferTiming = Literal["before_cleanup", "after_cleanup"]
CallerAction = Literal["none", "release", "propagate", "ignore"]

_DISPOSITIONS = ("ok", "retained_error", "consumed_error", "indeterminate")


@dataclass(frozen=True)
class ApiProfileOutcome:
    """Documented operation outcome mapped to a coarse ownership state.

    This table is research input, not runtime errno detection. Wrapper-level
    invalidation and underlying OS descriptor state remain separate fields.
    """

    profile: str
    outcome: str
    disposition: Disposition
    capability_state: str
    retry_allowed: bool
    error_obligation: str


API_PROFILE_OUTCOMES = (
    ApiProfileOutcome(
        "abstract_retained", "error", "retained_error", "live_owner",
        True, "API-specific retry or transfer",
    ),
    ApiProfileOutcome(
        "linux_close", "EIO/ENOSPC/EDQUOT/EINTR", "consumed_error",
        "descriptor_released", False, "diagnose or recover I/O side effect",
    ),
    ApiProfileOutcome(
        "linux_close", "EBADF", "indeterminate", "invalid_at_entry",
        False, "report invalid-handle/API invariant violation",
    ),
    ApiProfileOutcome(
        "posix_2024_close", "EINTR", "indeterminate",
        "open_or_closed_or_success", False,
        "requires implementation/outcome-specific reconciliation",
    ),
    ApiProfileOutcome(
        "go_os_file_close", "error", "consumed_error",
        "go_file_unusable", False, "preserve Close error; recover separately",
    ),
)


def api_profile_outcome(profile: str, outcome: str) -> ApiProfileOutcome:
    """Return the audited mapping for a named profile/outcome pair."""
    for item in API_PROFILE_OUTCOMES:
        if item.profile == profile and item.outcome == outcome:
            return item
    raise ValueError(f"unsupported API profile outcome: {profile}/{outcome}")


@dataclass(frozen=True)
class ReturnDispositionTrace:
    tag: str
    events: tuple[tuple[str, str, str], ...]
    errors: tuple[str, ...]
    resource_states: tuple[tuple[str, str], ...]
    caller_owner: str
    findings: tuple[str, ...] = ()


def run_return_disposition(
    *, body: BodyOutcome, transfer_timing: TransferTiming,
    local_disposition: Disposition, pending_handle_disposition: Disposition = "ok",
    caller_action: CallerAction = "none", caller_disposition: Disposition = "ok",
    output_carries_owned: bool = False,
) -> ReturnDispositionTrace:
    """Model one returned handle, one local resource, and one caller action.

    Dispositions are API contract inputs. ``domain_error_after_transfer`` is
    only defined for transfer before cleanup. The model does not parse source.
    """
    if body not in ("success", "domain_error_before_transfer", "domain_error_after_transfer"):
        raise ValueError("unsupported body outcome")
    if transfer_timing not in ("before_cleanup", "after_cleanup"):
        raise ValueError("unsupported transfer timing")
    if body == "domain_error_after_transfer" and transfer_timing != "before_cleanup":
        raise ValueError("domain error after transfer requires before-cleanup transfer")
    for name, value in (("local_disposition", local_disposition),
                        ("pending_handle_disposition", pending_handle_disposition),
                        ("caller_disposition", caller_disposition)):
        if value not in _DISPOSITIONS:
            raise ValueError(f"unsupported {name}")
    if caller_action not in ("none", "release", "propagate", "ignore"):
        raise ValueError("unsupported caller action")
    if type(output_carries_owned) is not bool:
        raise ValueError("output_carries_owned must be boolean")

    events: list[tuple[str, str, str]] = []
    errors: list[str] = []
    states: dict[str, str] = {}
    caller_owner = "none"
    returned = False

    def release(resource: str, disposition: Disposition) -> None:
        events.append(("release", resource, disposition))
        states[resource] = {
            "ok": "released",
            "retained_error": "live_cleanup_debt",
            "consumed_error": "consumed_with_error",
            "indeterminate": "ownership_unknown",
        }[disposition]
        if disposition != "ok":
            errors.append(f"{resource}:{disposition}")

    def transfer() -> None:
        nonlocal caller_owner, returned
        events.append(("transfer", "handle", "ok"))
        states["handle"] = "caller_owned"
        caller_owner = "caller"
        returned = True

    if body == "domain_error_before_transfer":
        release("local", local_disposition)
        release("handle", pending_handle_disposition)
        tag = "Err" if not errors else "ErrWithCleanupErrors"
        if errors:
            errors.insert(0, "domain_error")
    elif body == "domain_error_after_transfer":
        transfer()
        release("local", local_disposition)
        tag = "ErrorWithValue" if not errors else "DomainAndCleanupFailedWithValue"
        errors.insert(0, "domain_error")
    elif transfer_timing == "before_cleanup":
        transfer()
        release("local", local_disposition)
        tag = "OkWithValue" if not errors else "CleanupFailedWithValue"
    else:
        release("local", local_disposition)
        if local_disposition == "ok":
            transfer()
            tag = "OkWithValue"
        else:
            release("handle", pending_handle_disposition)
            tag = "StagedCleanupFailedWithoutValue"

    findings: list[str] = []
    if returned:
        if caller_action == "release":
            release("handle", caller_disposition)
            caller_owner = {
                "ok": "none",
                "retained_error": "caller_cleanup_debt",
                "consumed_error": "none",
                "indeterminate": "unknown",
            }[caller_disposition]
        elif caller_action == "propagate":
            if output_carries_owned:
                events.append(("propagate", "handle", "ok"))
                caller_owner = "upstream"
                states["handle"] = "upstream_owned"
            else:
                errors.append("propagation_drops_owned_value")
                findings.append("PROPAGATION_DROPS_OWNERSHIP")
                caller_owner = "caller"
                tag += "AndPropagationRejected"
        elif caller_action == "ignore":
            errors.append("ignored_owned_value")
            findings.append("LEAKED_OWNERSHIP")
            caller_owner = "caller_leaked"
            tag += "AndOwnershipIgnored"
    elif caller_action != "none":
        errors.append("caller_action_without_owned_value")
        findings.append("ACTION_WITHOUT_OWNED_VALUE")
        tag += "AndCallerActionWithoutValue"

    return ReturnDispositionTrace(
        tag, tuple(events), tuple(errors), tuple(sorted(states.items())),
        caller_owner, tuple(findings),
    )
