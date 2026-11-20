"""Finite ownership-obligation projection for COR-13 return/cleanup rules.

This intentionally does not extend the RT-03 expression evaluator. It models
the ownership slots and cleanup events for one fixed function-exit fixture so
that the candidate policies can be compared without pretending source-level
ownership analysis already exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Policy = Literal["reserve_then_commit", "transfer_then_cleanup", "reject_escape", "borrow_only"]
Body = Literal["return_handle", "return_error"]


@dataclass(frozen=True)
class Event:
    operation: Literal["acquire", "release", "reserve", "transfer"]
    resource: str
    outcome: Literal["ok", "error", "pending"]


@dataclass(frozen=True)
class Observation:
    outcome: Literal["ok", "error", "error_with_value", "static_reject"]
    returned: str | None
    events: tuple[Event, ...]
    owners: tuple[tuple[str, str], ...]


def run_return_cleanup(
    policy: Policy,
    *,
    body: Body = "return_handle",
    temporary_release_fails: bool = False,
    handle_release_fails: bool = False,
    caller_exits_after_return: bool = False,
) -> Observation:
    """Evaluate one owned-handle return with one callee-local cleanup.

    ``body`` selects whether the function returns the owned handle or a domain
    error. ``handle_release_fails`` describes cleanup of a pending result under
    staged commit, caller cleanup after transfer (including an error-with-value
    result), or callee cleanup on the error-return branch. On the handle-return
    branch, transfer-before-cleanup never releases the returned handle in the
    callee.
    """
    if policy not in ("reserve_then_commit", "transfer_then_cleanup", "reject_escape", "borrow_only"):
        raise ValueError("unsupported return/cleanup policy")
    if body not in ("return_handle", "return_error"):
        raise ValueError("unsupported function exit")
    if type(temporary_release_fails) is not bool or type(handle_release_fails) is not bool:
        raise ValueError("cleanup failure flags must be booleans")
    if type(caller_exits_after_return) is not bool:
        raise ValueError("caller_exits_after_return must be boolean")

    if policy in ("reject_escape", "borrow_only") and body == "return_handle":
        return Observation("static_reject", None, (), ())

    owners = {"temporary": "callee", "handle": "callee"}
    events = [Event("acquire", "temporary", "ok"), Event("acquire", "handle", "ok")]

    if body == "return_error":
        # The Result error branch returns no ownership. Both resources remain
        # callee-owned and leave their nested scopes in LIFO order.
        for resource, fails in (("handle", handle_release_fails),
                                ("temporary", temporary_release_fails)):
            events.append(Event("release", resource, "error" if fails else "ok"))
            if fails:
                owners[resource] = "callee_cleanup_debt"
            else:
                del owners[resource]
        return Observation("error", None, tuple(events), tuple(sorted(owners.items())))

    if policy == "reserve_then_commit":
        owners["handle"] = "pending_return"
        events.append(Event("reserve", "handle", "pending"))
    else:
        owners["handle"] = "caller"
        events.append(Event("transfer", "handle", "ok"))

    events.append(Event("release", "temporary", "error" if temporary_release_fails else "ok"))
    if temporary_release_fails:
        owners["temporary"] = "callee_cleanup_debt"
        if policy == "reserve_then_commit":
            events.append(Event("release", "handle", "error" if handle_release_fails else "ok"))
            if handle_release_fails:
                owners["handle"] = "pending_return_cleanup_debt"
            else:
                del owners["handle"]
            outcome = "error"
            returned = None
        else:
            # Preserve both the cleanup failure and the value's unique owner.
            outcome = "error_with_value"
            returned = "handle"
    else:
        del owners["temporary"]
        if policy == "reserve_then_commit":
            owners["handle"] = "caller"
            events.append(Event("transfer", "handle", "ok"))
        outcome = "ok"
        returned = "handle"

    if caller_exits_after_return and returned == "handle":
        events.append(Event("release", "handle", "error" if handle_release_fails else "ok"))
        if handle_release_fails:
            owners["handle"] = "caller_cleanup_debt"
        else:
            del owners["handle"]

    return Observation(outcome, returned, tuple(events), tuple(sorted(owners.items())))
