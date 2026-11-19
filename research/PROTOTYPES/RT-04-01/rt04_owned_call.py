"""Finite caller-side ownership check for COR-13 tagged call outcomes.

This is an isolated research model. It does not extend the RT-04 checker or
parse LLMLang source; callers provide explicit outcome branches and actions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CallCheck:
    status: str
    findings: tuple[str, ...]
    terminal_owners: tuple[tuple[str, str], ...]


def check_owned_call(result_type: Any, branches: Any) -> CallCheck:
    """Check explicit result branches for exactly-once handling of one handle.

    Supported result types are ``Result<Owned<Handle>, E>`` and
    ``ErrorWithValue<Owned<Handle>, E, C>``. Branch actions are ``release``,
    ``transfer``, ``propagate_owned``, ``ignore``, ``duplicate``, and ``use``.
    A propagated value must be represented by the caller's declared output
    type, supplied as ``output_carries_owned=True``.
    """
    if not isinstance(branches, dict) or not branches:
        raise ValueError("branches must be a non-empty outcome mapping")

    owned_result = False
    if isinstance(result_type, dict) and set(result_type) == {"Result"}:
        args = result_type["Result"]
        owned_result = (isinstance(args, list) and len(args) == 2 and
                        args[0] == {"Owned": "Handle"} and
                        isinstance(args[1], str))
        expected = {"ok", "error"}
    elif isinstance(result_type, dict) and set(result_type) == {"ErrorWithValue"}:
        args = result_type["ErrorWithValue"]
        owned_result = (isinstance(args, list) and len(args) == 3 and
                        args[0] == {"Owned": "Handle"} and
                        all(isinstance(x, str) for x in args[1:]))
        expected = {"ok", "error_with_value"}
    else:
        expected = set()

    if not owned_result:
        return CallCheck("UNKNOWN", ("UNKNOWN_OWNED_RESULT_TYPE",), ())
    if set(branches) != expected:
        return CallCheck("UNKNOWN", ("UNKNOWN_OUTCOME_COVERAGE",), ())

    findings: list[str] = []
    owners: list[tuple[str, str]] = []
    for outcome in sorted(expected):
        branch = branches[outcome]
        if not isinstance(branch, dict) or set(branch) - {"actions", "output_carries_owned"}:
            raise ValueError(f"{outcome} branch has invalid fields")
        actions = branch.get("actions")
        carries = branch.get("output_carries_owned", False)
        if not isinstance(actions, list) or any(a not in {
            "release", "transfer", "propagate_owned", "ignore", "duplicate", "use"
        } for a in actions):
            raise ValueError(f"{outcome}.actions contains an unsupported action")
        if type(carries) is not bool:
            raise ValueError("output_carries_owned must be boolean")

        value_present = outcome != "error" if "error" in expected else True
        if not value_present:
            if actions:
                findings.append(f"{outcome}:ACTION_WITHOUT_OWNED_VALUE")
            owners.append((outcome, "none"))
            continue

        terminal = "caller"
        if "duplicate" in actions:
            findings.append(f"{outcome}:DUPLICATE_OWNER")
        if "use" in actions and ("release" in actions or "transfer" in actions):
            first_terminal = min(i for i, a in enumerate(actions) if a in {"release", "transfer"})
            if any(a == "use" for a in actions[first_terminal + 1:]):
                findings.append(f"{outcome}:USE_AFTER_MOVE")
        terminal_actions = [a for a in actions if a in {"release", "transfer", "propagate_owned"}]
        if len(terminal_actions) > 1:
            findings.append(f"{outcome}:MULTIPLE_CONSUMPTIONS")
        elif not terminal_actions:
            findings.append(f"{outcome}:LEAKED_OWNERSHIP")
        else:
            action = terminal_actions[0]
            if action == "release":
                terminal = "released"
            elif action == "transfer":
                terminal = "transferred"
            elif carries:
                terminal = "caller_output"
            else:
                findings.append(f"{outcome}:PROPAGATION_DROPS_OWNERSHIP")
        owners.append((outcome, terminal))

    return CallCheck("REJECTED" if findings else "ACCEPTED",
                     tuple(findings), tuple(owners))


def check_owned_call_cfg(result_type: Any, outcome_cfgs: Any) -> CallCheck:
    """Check finite acyclic caller CFGs, preserving exact ownership at joins.

    Each outcome maps to ``{"entry": block, "blocks": {name: {"actions":
    [...], "successors": [...] }}, "output_carries_owned": bool}``. Every
    reachable terminal block must consume or return the obligation. Cycles and
    unsupported result types fail closed as UNKNOWN.
    """
    if isinstance(result_type, dict) and set(result_type) == {"Result"}:
        args = result_type["Result"]
        valid_type = (isinstance(args, list) and len(args) == 2 and
                      args[0] == {"Owned": "Handle"} and isinstance(args[1], str))
        expected = {"ok", "error"}
    elif isinstance(result_type, dict) and set(result_type) == {"ErrorWithValue"}:
        args = result_type["ErrorWithValue"]
        valid_type = (isinstance(args, list) and len(args) == 3 and
                      args[0] == {"Owned": "Handle"} and
                      all(isinstance(x, str) for x in args[1:]))
        expected = {"ok", "error_with_value"}
    else:
        valid_type, expected = False, set()
    if not valid_type:
        return CallCheck("UNKNOWN", ("UNKNOWN_OWNED_RESULT_TYPE",), ())
    if not isinstance(outcome_cfgs, dict) or set(outcome_cfgs) != expected:
        return CallCheck("UNKNOWN", ("UNKNOWN_OUTCOME_COVERAGE",), ())

    findings: list[str] = []
    terminal_owners: list[tuple[str, str]] = []
    allowed_actions = {"release", "transfer", "propagate_owned", "ignore", "duplicate", "use"}
    for outcome in sorted(expected):
        cfg = outcome_cfgs[outcome]
        if (not isinstance(cfg, dict) or set(cfg) != {"entry", "blocks", "output_carries_owned"}
                or type(cfg["output_carries_owned"]) is not bool):
            return CallCheck("UNKNOWN", (f"UNKNOWN_CFG:{outcome}",), ())
        entry, blocks = cfg["entry"], cfg["blocks"]
        if not isinstance(entry, str) or not isinstance(blocks, dict) or entry not in blocks:
            return CallCheck("UNKNOWN", (f"UNKNOWN_CFG:{outcome}",), ())
        normalized: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}
        malformed = False
        for name, block in blocks.items():
            if (not isinstance(name, str) or not isinstance(block, dict)
                    or set(block) - {"actions", "successors"}):
                malformed = True
                break
            actions, successors = block.get("actions", []), block.get("successors", [])
            if (not isinstance(actions, list) or any(action not in allowed_actions for action in actions)
                    or not isinstance(successors, list)
                    or any(not isinstance(target, str) or target not in blocks for target in successors)):
                malformed = True
                break
            normalized[name] = (tuple(actions), tuple(successors))
        if malformed:
            return CallCheck("UNKNOWN", (f"UNKNOWN_CFG:{outcome}",), ())

        # Reject cycles. This prototype enumerates finite acyclic control flow only.
        visiting: set[str] = set()
        visited: set[str] = set()
        cyclic = False
        def visit(block_name: str) -> None:
            nonlocal cyclic
            if block_name in visiting:
                cyclic = True
                return
            if block_name in visited:
                return
            visiting.add(block_name)
            for target in normalized[block_name][1]:
                visit(target)
            visiting.remove(block_name)
            visited.add(block_name)
        visit(entry)
        if cyclic:
            return CallCheck("UNKNOWN", (f"UNKNOWN_CYCLE:{outcome}",), ())

        incoming: dict[str, set[str]] = {name: set() for name in normalized}
        carries_input = not ("error" in expected and outcome == "error")
        incoming[entry].add("caller" if carries_input else "none")
        pending = [entry]
        while pending:
            block_name = pending.pop()
            states = incoming[block_name]
            if len(states) != 1:
                findings.append(f"{outcome}:{block_name}:OWNERSHIP_JOIN_MISMATCH")
                continue
            state = next(iter(states))
            actions, successors = normalized[block_name]
            current = state
            for action in actions:
                if current == "none":
                    findings.append(f"{outcome}:{block_name}:ACTION_WITHOUT_OWNED_VALUE")
                    continue
                if action == "use" and current != "caller":
                    findings.append(f"{outcome}:{block_name}:USE_AFTER_MOVE")
                elif action == "duplicate":
                    findings.append(f"{outcome}:{block_name}:DUPLICATE_OWNER")
                elif action == "ignore":
                    findings.append(f"{outcome}:{block_name}:IGNORED_OWNERSHIP")
                elif action in {"release", "transfer", "propagate_owned"}:
                    if current != "caller":
                        findings.append(f"{outcome}:{block_name}:MULTIPLE_CONSUMPTIONS")
                    elif action == "propagate_owned" and not cfg["output_carries_owned"]:
                        findings.append(f"{outcome}:{block_name}:PROPAGATION_DROPS_OWNERSHIP")
                    else:
                        current = {"release": "released", "transfer": "transferred",
                                   "propagate_owned": "caller_output"}[action]
            if not successors:
                if current == "caller":
                    findings.append(f"{outcome}:{block_name}:LEAKED_OWNERSHIP")
                else:
                    terminal_owners.append((outcome, current))
            for target in successors:
                before = len(incoming[target])
                incoming[target].add(current)
                if len(incoming[target]) != before:
                    pending.append(target)
    return CallCheck("REJECTED" if findings else "ACCEPTED",
                     tuple(sorted(set(findings))), tuple(sorted(terminal_owners)))
