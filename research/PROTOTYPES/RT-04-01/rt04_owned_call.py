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
