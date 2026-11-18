"""Finite executable reference semantics for an explicitly bounded RT-03 slice.

This is an exploratory interpreter for hand-authored expression trees. It is
not a LLMLang parser, compiler, or normative semantics.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


class SemanticError(ValueError):
    """The input is outside the supported semantic fragment."""


class _ExecutionCancelled(Exception):
    def __init__(self, reason: Any):
        self.reason = deepcopy(reason)


@dataclass(frozen=True)
class Trace:
    profile: str
    events: tuple[dict[str, Any], ...]
    result: Any
    final_state: dict[str, Any]
    final_files: dict[str, Any]
    final_resources: dict[str, Any]


def _record(expr: Any, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(expr, dict) or len(expr) != 1:
        raise SemanticError(f"{where} must be a single-key expression object")
    key = next(iter(expr))
    if key not in keys:
        raise SemanticError(f"unsupported {where} form: {key!r}")
    return expr


def evaluate(
    expression: Any,
    profile: str,
    *,
    declared_effects: tuple[str, ...] | list[str] = (),
    initial_state: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    network_responses: dict[str, Any] | None = None,
) -> Trace:
    """Evaluate the supported strict expression fragment under RT-03 A or D.

    Supported expressions:
      {"literal": value}
      {"add": [left, right]}                 # strict, left-to-right integers
      {"sequence": [expr, ...]}              # strict, left-to-right
      {"result_ok": expr} / {"result_error": expr}
      {"result_sequence": [Result expression, ...]}  # explicit first-error propagation
      {"cancel": reason}                       # terminal execution cancellation
      {"perform": {"effect": label, "operation": op, "payload": object}}

    Profile A rejects every perform expression. Profile D requires the effect
    label in declared_effects and interprets the finite handlers below:
      fs.read/read, fs.write/write, state.read/read, state.write/write,
      net.send/send.

    Result values are ordinary tagged data. They do not implicitly short-circuit
    sequence evaluation. This deliberately avoids selecting bind/exception
    propagation semantics that RT-03 has not yet decided.
    """
    if profile not in {"A", "D"}:
        raise SemanticError("profile must be A or D")
    if not isinstance(declared_effects, (list, tuple)) or any(
        not isinstance(x, str) or not x for x in declared_effects
    ):
        raise SemanticError("declared_effects must contain non-empty labels")
    if len(set(declared_effects)) != len(declared_effects):
        raise SemanticError("declared_effects contains duplicates")
    if initial_state is not None and not isinstance(initial_state, dict):
        raise SemanticError("initial_state must be an object")
    if files is not None and not isinstance(files, dict):
        raise SemanticError("files must be an object")
    if network_responses is not None and not isinstance(network_responses, dict):
        raise SemanticError("network_responses must be an object")

    allowed = set(declared_effects)
    state = deepcopy(initial_state or {})
    file_store = deepcopy(files or {})
    responses = deepcopy(network_responses or {})
    events: list[dict[str, Any]] = []
    resources: dict[str, Any] = {}

    def perform(spec: Any) -> Any:
        if profile == "A":
            raise SemanticError("Profile A is pure: perform is not permitted")
        if not isinstance(spec, dict) or set(spec) != {"effect", "operation", "payload"}:
            raise SemanticError("perform requires effect, operation, and payload")
        effect, operation, payload = spec["effect"], spec["operation"], spec["payload"]
        if not isinstance(effect, str) or not effect or not isinstance(operation, str) or not operation:
            raise SemanticError("effect and operation must be non-empty strings")
        if not isinstance(payload, dict):
            raise SemanticError("effect payload must be an object")
        if effect not in allowed:
            raise SemanticError(f"effect {effect!r} is not declared")
        outcome: Any

        if (effect, operation) == ("fs.read", "read"):
            if set(payload) != {"path"} or not isinstance(payload["path"], str):
                raise SemanticError("fs.read/read requires a string path")
            path = payload["path"]
            if path in file_store:
                outcome = {"ok": deepcopy(file_store[path])}
            else:
                outcome = {"error": {"kind": "NotFound", "path": path}}
        elif (effect, operation) == ("fs.write", "write"):
            if set(payload) != {"path", "value"} or not isinstance(payload["path"], str):
                raise SemanticError("fs.write/write requires path and value")
            file_store[payload["path"]] = deepcopy(payload["value"])
            outcome = {"ok": None}
        elif (effect, operation) == ("state.read", "read"):
            if set(payload) != {"key"} or not isinstance(payload["key"], str):
                raise SemanticError("state.read/read requires a string key")
            outcome = {"ok": deepcopy(state.get(payload["key"]))}
        elif (effect, operation) == ("state.write", "write"):
            if set(payload) != {"key", "value"} or not isinstance(payload["key"], str):
                raise SemanticError("state.write/write requires key and value")
            state[payload["key"]] = deepcopy(payload["value"])
            outcome = {"ok": None}
        elif (effect, operation) == ("net.send", "send"):
            if set(payload) != {"endpoint", "message"} or not isinstance(payload["endpoint"], str):
                raise SemanticError("net.send/send requires endpoint and message")
            endpoint = payload["endpoint"]
            if endpoint in responses:
                outcome = {"ok": deepcopy(responses[endpoint])}
            else:
                outcome = {"error": {"kind": "NoFixtureResponse", "endpoint": endpoint}}
        elif (effect, operation) == ("resource.use", "use"):
            if set(payload) != {"id"} or not isinstance(payload["id"], str):
                raise SemanticError("resource.use/use requires a resource id")
            resource_id = payload["id"]
            if resource_id in resources:
                outcome = {"ok": deepcopy(resources[resource_id])}
            else:
                outcome = {"error": {"kind": "ResourceUnavailable", "resource": resource_id}}
        else:
            raise SemanticError(f"no reference handler for {effect!r}/{operation!r}")

        events.append({
            "effect": effect,
            "operation": operation,
            "payload": deepcopy(payload),
            "outcome": deepcopy(outcome),
        })
        return deepcopy(outcome)

    def visit(node: Any) -> Any:
        expr = _record(node, {"literal", "add", "sequence", "result_ok", "result_error", "result_sequence", "cancel", "with_resource", "perform"}, "expression")
        op, arg = next(iter(expr.items()))
        if op == "literal":
            return deepcopy(arg)
        if op == "add":
            if not isinstance(arg, list) or len(arg) != 2:
                raise SemanticError("add requires exactly two operands")
            left = visit(arg[0])
            right = visit(arg[1])
            if type(left) is not int or type(right) is not int:
                raise SemanticError("add operands must evaluate to integers")
            return left + right
        if op == "sequence":
            if not isinstance(arg, list) or not arg:
                raise SemanticError("sequence requires a non-empty expression list")
            value: Any = None
            for item in arg:
                value = visit(item)
            return value
        if op == "result_ok":
            return {"ok": visit(arg)}
        if op == "result_error":
            return {"error": visit(arg)}
        if op == "result_sequence":
            if not isinstance(arg, list) or not arg:
                raise SemanticError("result_sequence requires a non-empty expression list")
            value: Any = None
            for item in arg:
                value = visit(item)
                if not isinstance(value, dict) or len(value) != 1 or next(iter(value)) not in {"ok", "error"}:
                    raise SemanticError("result_sequence items must evaluate to Result-shaped values")
                if "error" in value:
                    return deepcopy(value)
            return deepcopy(value)
        if op == "cancel":
            raise _ExecutionCancelled(arg)
        if op == "with_resource":
            if profile != "D":
                raise SemanticError("Profile A is pure: resource scopes are not permitted")
            required = {"id", "value", "body"}
            if not isinstance(arg, dict) or not required.issubset(arg) or set(arg) - (required | {"acquire_fails", "release_fails"}):
                raise SemanticError("with_resource requires id, value, body, and optional failure flags")
            resource_id = arg["id"]
            if not isinstance(resource_id, str) or not resource_id:
                raise SemanticError("with_resource id must be a non-empty string")
            for flag in ("acquire_fails", "release_fails"):
                if flag in arg and type(arg[flag]) is not bool:
                    raise SemanticError(f"{flag} must be boolean")
            acquire_payload = {"id": resource_id, "value": deepcopy(arg["value"])}
            if arg.get("acquire_fails", False):
                outcome = {"error": {"kind": "AcquireFailed", "resource": resource_id}}
                events.append({"effect": "resource.acquire", "operation": "acquire", "payload": acquire_payload, "outcome": deepcopy(outcome)})
                return outcome
            if resource_id in resources:
                outcome = {"error": {"kind": "AlreadyAcquired", "resource": resource_id}}
                events.append({"effect": "resource.acquire", "operation": "acquire", "payload": acquire_payload, "outcome": deepcopy(outcome)})
                return outcome
            resources[resource_id] = deepcopy(arg["value"])
            events.append({"effect": "resource.acquire", "operation": "acquire", "payload": acquire_payload, "outcome": {"ok": {"id": resource_id}}})
            try:
                body_value = visit(arg["body"])
            except _ExecutionCancelled as cancelled:
                release_outcome = ({"error": {"kind": "ReleaseFailed", "resource": resource_id}}
                                   if arg.get("release_fails", False) else {"ok": None})
                events.append({"effect": "resource.release", "operation": "release", "payload": {"id": resource_id}, "outcome": deepcopy(release_outcome)})
                if "error" not in release_outcome:
                    resources.pop(resource_id, None)
                    raise
                raise _ExecutionCancelled({"reason": deepcopy(cancelled.reason), "cleanup_errors": [release_outcome["error"]]})
            except Exception:
                release_outcome = ({"error": {"kind": "ReleaseFailed", "resource": resource_id}}
                                   if arg.get("release_fails", False) else {"ok": None})
                events.append({"effect": "resource.release", "operation": "release", "payload": {"id": resource_id}, "outcome": deepcopy(release_outcome)})
                if "error" not in release_outcome:
                    resources.pop(resource_id, None)
                raise
            release_outcome = ({"error": {"kind": "ReleaseFailed", "resource": resource_id}}
                               if arg.get("release_fails", False) else {"ok": None})
            events.append({"effect": "resource.release", "operation": "release", "payload": {"id": resource_id}, "outcome": deepcopy(release_outcome)})
            if "error" not in release_outcome:
                resources.pop(resource_id, None)
                return body_value
            if isinstance(body_value, dict) and set(body_value) == {"error"}:
                return {"error": {"kind": "CleanupFailed", "primary": deepcopy(body_value["error"]), "cleanup": deepcopy(release_outcome["error"])}}
            return {"error": {"kind": "CleanupFailed", "cleanup": deepcopy(release_outcome["error"])}}
        if op == "perform":
            return perform(arg)
        raise AssertionError("unreachable expression form")

    try:
        result = visit(expression)
    except _ExecutionCancelled as cancelled:
        result = {"cancelled": deepcopy(cancelled.reason)}
    return Trace(
        profile=profile,
        events=tuple(deepcopy(events)),
        result=deepcopy(result),
        final_state=deepcopy(state),
        final_files=deepcopy(file_store),
        final_resources=deepcopy(resources),
    )
