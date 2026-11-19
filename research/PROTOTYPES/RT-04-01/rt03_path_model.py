"""Independent finite path model for RT-03 branch/resource cleanup scenarios.

This model does not execute expressions, effects, or values and imports neither
RT-03 evaluator. It enumerates structural control-flow paths and tracks only
resource acquisition/release obligations, cancellation, and Result short-circuit
markers. It is an oracle for the bounded fixture fragment, not source-level
path-completeness evidence or a language semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PathOutcome:
    branch_choices: tuple[tuple[str, bool], ...]
    resource_events: tuple[tuple[str, str, bool], ...]
    active_resources: tuple[str, ...]
    terminal: str
    result_tag: str | None
    cleanup_errors: tuple[str, ...]


@dataclass(frozen=True)
class _State:
    active: tuple[tuple[str, bool], ...] = ()
    choices: tuple[tuple[str, bool], ...] = ()
    events: tuple[tuple[str, str, bool], ...] = ()
    terminal: str = "normal"
    result_tag: str | None = None
    cleanup_errors: tuple[str, ...] = ()
    leaked: tuple[str, ...] = ()


def enumerate_paths(expression: Any) -> tuple[PathOutcome, ...]:
    """Enumerate all structural paths for the supported RT-03 control fragment.

    Unknown conditions fork into both branches. Literal boolean conditions select
    one branch. Repeated occurrences of the same unknown_bool marker reuse its
    earlier choice on that path. A resource is released on
    normal/Result-error/cancelled body exit.
    Failed release leaves it active and is reported without erasing cancellation.
    """
    marker_by_path: dict[str, Any] = {}

    def discover_markers(node: Any, path: str) -> None:
        """Index direct symbolic conditions so repeated names stay correlated."""
        if not isinstance(node, dict) or len(node) != 1:
            return
        op, arg = next(iter(node.items()))
        if op == "if" and isinstance(arg, dict):
            condition = arg.get("condition")
            if isinstance(condition, dict) and set(condition) == {"unknown_bool"}:
                marker_by_path[path] = condition["unknown_bool"]
            if "then" in arg:
                discover_markers(arg["then"], f"{path}.then")
            if "else" in arg:
                discover_markers(arg["else"], f"{path}.else")
        elif op == "with_resource" and isinstance(arg, dict) and "body" in arg:
            discover_markers(arg["body"], f"{path}.body")
        elif op in {"result_ok", "result_error"}:
            discover_markers(arg, f"{path}.{op}")
        elif op in {"sequence", "result_sequence", "add"} and isinstance(arg, list):
            for index, item in enumerate(arg):
                discover_markers(item, f"{path}.{op}[{index}]")

    discover_markers(expression, "$")

    def walk(node: Any, state: _State, path: str) -> list[_State]:
        if state.terminal == "cancelled":
            return [state]
        if not isinstance(node, dict) or len(node) != 1:
            raise ValueError(f"invalid expression at {path}")
        op, arg = next(iter(node.items()))

        if op in {"literal", "perform", "unknown_bool"}:
            return [_State(state.active, state.choices, state.events,
                            state.terminal, None, state.cleanup_errors, state.leaked)]
        if op == "add":
            if not isinstance(arg, list) or len(arg) != 2:
                raise ValueError(f"invalid add at {path}")
            states = walk(arg[0], state, f"{path}.add[0]")
            states = [next_state for current in states
                      for next_state in ([current] if current.terminal == "cancelled"
                                         else walk(arg[1], current, f"{path}.add[1]"))]
            return [_State(current.active, current.choices, current.events,
                           current.terminal, None, current.cleanup_errors, current.leaked)
                    for current in states]
        if op == "cancel":
            return [_State(state.active, state.choices, state.events,
                           "cancelled", None, state.cleanup_errors, state.leaked)]
        if op in {"result_ok", "result_error"}:
            states = walk(arg, state, f"{path}.{op}")
            tag = "ok" if op == "result_ok" else "error"
            return [
                current if current.terminal == "cancelled" else _State(
                    current.active, current.choices, current.events,
                    current.terminal, tag, current.cleanup_errors, current.leaked,
                )
                for current in states
            ]
        if op == "sequence":
            if not isinstance(arg, list) or not arg:
                raise ValueError(f"invalid sequence at {path}")
            states = [state]
            for index, item in enumerate(arg):
                states = [next_state for current in states
                          for next_state in walk(item, current, f"{path}.sequence[{index}]")]
            return states
        if op == "result_sequence":
            if not isinstance(arg, list) or not arg:
                raise ValueError(f"invalid result_sequence at {path}")
            states = [state]
            for index, item in enumerate(arg):
                next_states = []
                for current in states:
                    if current.terminal == "cancelled" or current.result_tag == "error":
                        next_states.append(current)
                    else:
                        next_states.extend(walk(item, current, f"{path}.result_sequence[{index}]"))
                states = next_states
            return states
        if op == "if":
            if not isinstance(arg, dict) or set(arg) != {"condition", "then", "else"}:
                raise ValueError(f"invalid if at {path}")
            condition = arg["condition"]
            literal_bool = (
                isinstance(condition, dict) and set(condition) == {"literal"}
                and type(condition["literal"]) is bool
            )
            abstract_bool = (
                isinstance(condition, dict) and set(condition) == {"unknown_bool"}
            )
            if isinstance(condition, dict) and set(condition) == {"literal"} and not literal_bool:
                raise ValueError(f"if condition must be boolean at {path}")
            if not literal_bool and not abstract_bool and not (
                isinstance(condition, dict) and set(condition) == {"cancel"}
            ):
                raise ValueError(
                    f"path model requires a literal boolean, unknown_bool marker, "
                    f"or cancellation condition at {path}"
                )
            condition_states = walk(condition, state, f"{path}.condition")
            outcomes: list[_State] = []
            for condition_state in condition_states:
                if condition_state.terminal == "cancelled":
                    outcomes.append(condition_state)
                    continue
                if literal_bool:
                    choices = ((condition["literal"],),)
                elif abstract_bool:
                    marker = condition["unknown_bool"]
                    prior = [
                        choice for branch_path, choice in state.choices
                        if marker_by_path.get(branch_path) == marker
                    ]
                    choices = ((prior[-1],),) if prior else ((True,), (False,))
                else:
                    choices = ((True,), (False,))
                for (choice,) in choices:
                    selected = _State(
                        condition_state.active,
                        condition_state.choices + ((path, choice),),
                        condition_state.events,
                        condition_state.terminal,
                        None,
                        condition_state.cleanup_errors,
                        condition_state.leaked,
                    )
                    chosen = arg["then"] if choice else arg["else"]
                    outcomes.extend(walk(chosen, selected,
                                         f"{path}.{'then' if choice else 'else'}"))
            return outcomes
        if op == "with_resource":
            required = {"id", "value", "body"}
            if not isinstance(arg, dict) or not required.issubset(arg) or set(arg) - (
                required | {"acquire_fails", "release_fails"}
            ):
                raise ValueError(f"invalid with_resource at {path}")
            resource_id = arg["id"]
            if not isinstance(resource_id, str) or not resource_id:
                raise ValueError(f"invalid resource id at {path}")
            acquire_fails = arg.get("acquire_fails", False)
            release_fails = arg.get("release_fails", False)
            if type(acquire_fails) is not bool or type(release_fails) is not bool:
                raise ValueError(f"invalid resource failure flag at {path}")
            if acquire_fails or any(existing == resource_id for existing, _ in state.active) or resource_id in state.leaked:
                failed = _State(state.active, state.choices,
                                state.events + (("acquire", resource_id, False),),
                                state.terminal, "error", state.cleanup_errors, state.leaked)
                return [failed]
            acquired = _State(state.active + ((resource_id, release_fails),),
                              state.choices,
                              state.events + (("acquire", resource_id, True),),
                              state.terminal, state.result_tag, state.cleanup_errors, state.leaked)
            body_states = walk(arg["body"], acquired, f"{path}.body")
            released_states: list[_State] = []
            for body_state in body_states:
                active = list(body_state.active)
                if not active or active[-1][0] != resource_id:
                    raise ValueError(f"non-LIFO resource state at {path}")
                active.pop()
                release_ok = not release_fails
                events = body_state.events + (("release", resource_id, release_ok),)
                if release_ok:
                    released_states.append(_State(tuple(active), body_state.choices,
                                                  events, body_state.terminal,
                                                  body_state.result_tag,
                                                  body_state.cleanup_errors, body_state.leaked))
                elif body_state.terminal == "cancelled":
                    released_states.append(_State(
                        tuple(active),
                        body_state.choices, events, "cancelled", None,
                        body_state.cleanup_errors + (resource_id,),
                        body_state.leaked + (resource_id,),
                    ))
                else:
                    released_states.append(_State(
                        tuple(active),
                        body_state.choices, events, body_state.terminal, "error",
                        body_state.cleanup_errors + (resource_id,),
                        body_state.leaked + (resource_id,),
                    ))
            return released_states
        raise ValueError(f"unsupported expression form at {path}: {op!r}")

    states = walk(expression, _State(), "$")
    return tuple(PathOutcome(
        branch_choices=state.choices,
        resource_events=state.events,
        active_resources=tuple(sorted(tuple(resource_id for resource_id, _ in state.active) + state.leaked)),
        terminal=state.terminal,
        result_tag=state.result_tag,
        cleanup_errors=state.cleanup_errors,
    ) for state in states)
