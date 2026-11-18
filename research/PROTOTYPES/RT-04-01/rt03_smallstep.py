"""Independent small-step machine for the bounded RT-03 A/D experiment.

This intentionally does not import rt03_reference.py. It uses an explicit
control stack/value stack rather than recursive evaluation.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


class MachineError(ValueError):
    pass


@dataclass(frozen=True)
class MachineTrace:
    profile: str
    events: tuple[dict[str, Any], ...]
    result: Any
    final_state: dict[str, Any]
    final_files: dict[str, Any]


def run_small_step(
    expression: Any,
    profile: str,
    *,
    declared_effects: tuple[str, ...] | list[str] = (),
    initial_state: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    network_responses: dict[str, Any] | None = None,
) -> MachineTrace:
    """Run the shared fragment using explicit evaluation and continuation stacks.

    result_sequence explicitly propagates the first Result error; ordinary
    sequence remains strict. A cancel expression terminates the machine and
    discards pending continuations, producing a distinct cancelled outcome.
    """
    if profile not in {"A", "D"}:
        raise MachineError("profile must be A or D")
    if not isinstance(declared_effects, (list, tuple)) or any(
        not isinstance(x, str) or not x for x in declared_effects
    ) or len(set(declared_effects)) != len(declared_effects):
        raise MachineError("declared_effects must contain unique non-empty labels")
    if initial_state is not None and not isinstance(initial_state, dict):
        raise MachineError("initial_state must be an object")
    if files is not None and not isinstance(files, dict):
        raise MachineError("files must be an object")
    if network_responses is not None and not isinstance(network_responses, dict):
        raise MachineError("network_responses must be an object")

    allowed = set(declared_effects)
    store = deepcopy(initial_state or {})
    file_map = deepcopy(files or {})
    responses = deepcopy(network_responses or {})
    events: list[dict[str, Any]] = []
    values: list[Any] = []
    # Tasks are either ("eval", expression) or explicit continuations.
    tasks: list[tuple[Any, ...]] = [("eval", expression)]

    def effect_step(spec: Any) -> Any:
        if profile != "D":
            raise MachineError("Profile A is pure: perform is not permitted")
        if not isinstance(spec, dict) or set(spec) != {"effect", "operation", "payload"}:
            raise MachineError("perform requires effect, operation, and payload")
        label, operation, data = spec["effect"], spec["operation"], spec["payload"]
        if not isinstance(label, str) or not label or not isinstance(operation, str) or not operation:
            raise MachineError("effect and operation must be non-empty strings")
        if not isinstance(data, dict):
            raise MachineError("effect payload must be an object")
        if label not in allowed:
            raise MachineError(f"effect {label!r} is not declared")

        if label == "fs.read" and operation == "read" and set(data) == {"path"} and isinstance(data["path"], str):
            path = data["path"]
            result = {"ok": deepcopy(file_map[path])} if path in file_map else {
                "error": {"kind": "NotFound", "path": path}
            }
        elif label == "fs.write" and operation == "write" and set(data) == {"path", "value"} and isinstance(data["path"], str):
            file_map[data["path"]] = deepcopy(data["value"])
            result = {"ok": None}
        elif label == "state.read" and operation == "read" and set(data) == {"key"} and isinstance(data["key"], str):
            result = {"ok": deepcopy(store.get(data["key"]))}
        elif label == "state.write" and operation == "write" and set(data) == {"key", "value"} and isinstance(data["key"], str):
            store[data["key"]] = deepcopy(data["value"])
            result = {"ok": None}
        elif label == "net.send" and operation == "send" and set(data) == {"endpoint", "message"} and isinstance(data["endpoint"], str):
            endpoint = data["endpoint"]
            result = {"ok": deepcopy(responses[endpoint])} if endpoint in responses else {
                "error": {"kind": "NoFixtureResponse", "endpoint": endpoint}
            }
        else:
            if label in {"fs.read", "fs.write", "state.read", "state.write", "net.send"}:
                raise MachineError(f"invalid payload or operation for {label!r}/{operation!r}")
            raise MachineError(f"no reference handler for {label!r}/{operation!r}")

        events.append({
            "effect": label,
            "operation": operation,
            "payload": deepcopy(data),
            "outcome": deepcopy(result),
        })
        return result

    while tasks:
        task = tasks.pop()
        tag = task[0]

        if tag == "eval":
            node = task[1]
            if not isinstance(node, dict) or len(node) != 1:
                raise MachineError("expression must be a single-key object")
            op, arg = next(iter(node.items()))
            if op == "literal":
                values.append(deepcopy(arg))
            elif op == "add":
                if not isinstance(arg, list) or len(arg) != 2:
                    raise MachineError("add requires exactly two operands")
                tasks.append(("add_left_done", arg[1]))
                tasks.append(("eval", arg[0]))
            elif op == "sequence":
                if not isinstance(arg, list) or not arg:
                    raise MachineError("sequence requires a non-empty expression list")
                tasks.append(("sequence_done", arg[1:]))
                tasks.append(("eval", arg[0]))
            elif op in {"result_ok", "result_error"}:
                tasks.append(("result_done", op))
                tasks.append(("eval", arg))
            elif op == "result_sequence":
                if not isinstance(arg, list) or not arg:
                    raise MachineError("result_sequence requires a non-empty expression list")
                tasks.append(("result_sequence_done", arg[1:]))
                tasks.append(("eval", arg[0]))
            elif op == "cancel":
                # Cancellation is a terminal control outcome, not a Result value.
                # Discard pending continuations so no later expression executes.
                tasks.clear()
                values.clear()
                values.append({"cancelled": deepcopy(arg)})
                break
            elif op == "perform":
                values.append(effect_step(arg))
            else:
                raise MachineError(f"unsupported expression form: {op!r}")

        elif tag == "add_left_done":
            left = values.pop()
            tasks.append(("add_right_done", left))
            tasks.append(("eval", task[1]))

        elif tag == "add_right_done":
            right = values.pop()
            left = task[1]
            if type(left) is not int or type(right) is not int:
                raise MachineError("add operands must evaluate to integers")
            values.append(left + right)

        elif tag == "sequence_done":
            remaining = task[1]
            if remaining:
                values.pop()  # Discard the preceding expression's value.
                tasks.append(("sequence_done", remaining[1:]))
                tasks.append(("eval", remaining[0]))

        elif tag == "result_done":
            values.append({task[1] == "result_ok" and "ok" or "error": values.pop()})

        elif tag == "result_sequence_done":
            remaining = task[1]
            current = values[-1]
            if not isinstance(current, dict) or len(current) != 1 or next(iter(current)) not in {"ok", "error"}:
                raise MachineError("result_sequence items must evaluate to Result-shaped values")
            if "error" not in current and remaining:
                values.pop()
                tasks.append(("result_sequence_done", remaining[1:]))
                tasks.append(("eval", remaining[0]))

        else:
            raise MachineError(f"invalid machine continuation: {tag!r}")

    if len(values) != 1:
        raise MachineError("machine ended with an invalid value-stack shape")
    return MachineTrace(
        profile=profile,
        events=tuple(deepcopy(events)),
        result=deepcopy(values[0]),
        final_state=deepcopy(store),
        final_files=deepcopy(file_map),
    )
