"""Cross-probe for fuel exhaustion at an owned-return cleanup boundary.

This combines the candidate dimensions from COR-13 and the RT-03 fuel cleanup
probe. It is one explicitly chosen rule: fuel exhaustion prevents normal
commit; transfer-first keeps the handle with the caller; staged return disposes
the pending handle; reserved cleanup can run and fail independently. It is not
LLMLang semantics and does not execute arbitrary cleanup code.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ReturnTiming = Literal["reserve_then_commit", "transfer_then_cleanup"]
CleanupBudget = Literal["reserved", "depleted"]


@dataclass(frozen=True)
class Observation:
    return_timing: ReturnTiming
    cleanup_budget: CleanupBudget
    fuel_exhausted: bool
    returned_value: str | None
    effect_trace: tuple[str, ...]
    cleanup_trace: tuple[tuple[str, str], ...]
    cleanup_blocked: tuple[str, ...]
    owners: tuple[tuple[str, str], ...]


def run_fuel_exhaustion_at_return(
    return_timing: ReturnTiming,
    cleanup_budget: CleanupBudget,
    *,
    temporary_release_fails: bool = False,
    pending_handle_release_fails: bool = False,
) -> Observation:
    """Observe a completed return expression followed by zero-fuel cleanup.

    ``returned_value`` records whether the handle is delivered to the caller
    alongside the non-normal fuel outcome. Under staged return, this candidate
    rule instead disposes of the uncommitted value during cleanup.
    """
    if return_timing not in {"reserve_then_commit", "transfer_then_cleanup"}:
        raise ValueError(f"unsupported return timing: {return_timing}")
    if cleanup_budget not in {"reserved", "depleted"}:
        raise ValueError(f"unsupported cleanup budget: {cleanup_budget}")
    if type(temporary_release_fails) is not bool or type(pending_handle_release_fails) is not bool:
        raise ValueError("cleanup failure flags must be booleans")

    owners = {"temporary": "callee", "handle": "callee"}
    effects = ("write:recorded",)
    cleanup: list[tuple[str, str]] = []
    blocked: list[str] = []

    if return_timing == "transfer_then_cleanup":
        owners["handle"] = "caller"
        returned_value = "handle"
    else:
        owners["handle"] = "pending_return"
        returned_value = None

    if cleanup_budget == "depleted":
        owners["temporary"] = "callee_cleanup_debt"
        blocked.append("temporary")
        if return_timing == "reserve_then_commit":
            owners["handle"] = "pending_return_cleanup_debt"
            blocked.append("handle")
    else:
        cleanup.append(("temporary", "error" if temporary_release_fails else "ok"))
        if temporary_release_fails:
            owners["temporary"] = "callee_cleanup_debt"
        else:
            del owners["temporary"]

        if return_timing == "reserve_then_commit":
            cleanup.append(("handle", "error" if pending_handle_release_fails else "ok"))
            if pending_handle_release_fails:
                owners["handle"] = "pending_return_cleanup_debt"
            else:
                del owners["handle"]

    return Observation(
        return_timing,
        cleanup_budget,
        True,
        returned_value,
        effects,
        tuple(cleanup),
        tuple(blocked),
        tuple(sorted(owners.items())),
    )


if __name__ == "__main__":
    cases = (
        ("reserve_then_commit", "reserved", False, False),
        ("reserve_then_commit", "reserved", True, True),
        ("reserve_then_commit", "depleted", False, False),
        ("transfer_then_cleanup", "reserved", True, False),
        ("transfer_then_cleanup", "depleted", False, False),
    )
    for timing, budget, temp_fails, handle_fails in cases:
        print(run_fuel_exhaustion_at_return(
            timing, budget,
            temporary_release_fails=temp_fails,
            pending_handle_release_fails=handle_fails,
        ))
