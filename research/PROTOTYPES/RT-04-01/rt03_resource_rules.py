"""Independent outcome-algebra model for bounded RT-03 resource scopes.

The rules are expressed as an algebra over body outcomes and acquired scope
frames. This module imports neither RT-03 evaluator nor the structural path
enumerator. It models exact cleanup result precedence, cancellation aggregation,
resource events, and resources retained after failed release.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class ResourceFrame:
    resource_id: str
    value: Any
    release_fails: bool = False


@dataclass(frozen=True)
class BodyOutcome:
    kind: Literal["normal", "result_error", "cancelled"]
    payload: Any = None


@dataclass(frozen=True)
class ResourceTrace:
    events: tuple[dict[str, Any], ...]
    result: Any
    final_resources: dict[str, Any]


def derive_resource_trace(
    frames: tuple[ResourceFrame, ...] | list[ResourceFrame],
    body: BodyOutcome,
    *,
    acquire_fail_at: int | None = None,
) -> ResourceTrace:
    """Derive the trace by applying the resource-scope outcome rules.

    Frames are ordered outermost to innermost. An acquisition failure at index
    i prevents acquisition of i and all inner frames, skips the body, and
    becomes an ordinary Result error that is then observed by outer scopes.
    """
    frames = tuple(frames)
    if body.kind not in {"normal", "result_error", "cancelled"}:
        raise ValueError("unsupported body outcome")
    if acquire_fail_at is not None and (
        type(acquire_fail_at) is not int or not 0 <= acquire_fail_at < len(frames)
    ):
        raise ValueError("acquire_fail_at must identify an existing frame")
    if any(not isinstance(frame, ResourceFrame) for frame in frames):
        raise ValueError("frames must contain ResourceFrame values")
    if any(not isinstance(frame.resource_id, str) or not frame.resource_id for frame in frames):
        raise ValueError("resource IDs must be non-empty strings")
    if len({frame.resource_id for frame in frames}) != len(frames):
        raise ValueError("resource IDs must be unique")
    if any(type(frame.release_fails) is not bool for frame in frames):
        raise ValueError("release_fails must be boolean")

    events: list[dict[str, Any]] = []
    active: dict[str, Any] = {}
    acquired: list[ResourceFrame] = []

    for index, frame in enumerate(frames):
        payload = {"id": frame.resource_id, "value": deepcopy(frame.value)}
        if index == acquire_fail_at:
            outcome = {"error": {"kind": "AcquireFailed", "resource": frame.resource_id}}
            events.append({
                "effect": "resource.acquire", "operation": "acquire",
                "payload": payload, "outcome": deepcopy(outcome),
            })
            current = BodyOutcome("result_error", outcome["error"])
            break
        active[frame.resource_id] = deepcopy(frame.value)
        acquired.append(frame)
        events.append({
            "effect": "resource.acquire", "operation": "acquire",
            "payload": payload, "outcome": {"ok": {"id": frame.resource_id}},
        })
    else:
        current = body

    if current.kind == "normal":
        result = deepcopy(current.payload)
    elif current.kind == "result_error":
        result = {"error": deepcopy(current.payload)}
    else:
        result = {"cancelled": deepcopy(current.payload)}

    cleanup_errors: list[dict[str, Any]] = []
    for frame in reversed(acquired):
        cleanup_error = {"kind": "ReleaseFailed", "resource": frame.resource_id}
        release_outcome = (
            {"error": cleanup_error} if frame.release_fails else {"ok": None}
        )
        events.append({
            "effect": "resource.release", "operation": "release",
            "payload": {"id": frame.resource_id},
            "outcome": deepcopy(release_outcome),
        })
        if not frame.release_fails:
            active.pop(frame.resource_id)
            continue

        if isinstance(result, dict) and set(result) == {"cancelled"}:
            cleanup_errors.append(deepcopy(cleanup_error))
        else:
            primary = result.get("error") if (
                isinstance(result, dict) and set(result) == {"error"}
            ) else None
            failure: dict[str, Any] = {"kind": "CleanupFailed", "cleanup": cleanup_error}
            if primary is not None:
                failure["primary"] = deepcopy(primary)
            result = {"error": failure}

    if isinstance(result, dict) and set(result) == {"cancelled"} and cleanup_errors:
        result = {"cancelled": {
            "reason": deepcopy(result["cancelled"]),
            "cleanup_errors": cleanup_errors,
        }}

    return ResourceTrace(
        events=tuple(events),
        result=deepcopy(result),
        final_resources=deepcopy(active),
    )
