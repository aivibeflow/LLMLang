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


@dataclass(frozen=True)
class FlowExecution:
    status: str
    events: tuple[str, ...]
    terminal_owner: str
    findings: tuple[str, ...] = ()


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
    [...], "successors": [...] }}, "output_carries_owned": bool}``. A block
    may instead declare ``release_attempt: true`` and map ``successors`` as
    ``{"ok": block, "error": block}``; success consumes the owner and failure
    preserves it with cleanup debt. Every terminal path must discharge or
    propagate the obligation. Cycles and unsupported types return UNKNOWN.
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
        normalized: dict[str, tuple[tuple[str, ...], tuple[tuple[str, str | None], ...], bool]] = {}
        malformed = False
        for name, block in blocks.items():
            if (not isinstance(name, str) or not isinstance(block, dict)
                    or set(block) - {"actions", "successors", "release_attempt"}):
                malformed = True
                break
            actions, successors = block.get("actions", []), block.get("successors", [])
            attempt = block.get("release_attempt", False)
            if type(attempt) is not bool or not isinstance(actions, list) or any(
                action not in allowed_actions for action in actions
            ):
                malformed = True
                break
            if attempt:
                if (not isinstance(successors, dict) or set(successors) != {"ok", "error"}
                        or any(not isinstance(target, str) or target not in blocks
                               for target in successors.values())
                        or any(action in {"release", "transfer", "propagate_owned"}
                               for action in actions)):
                    malformed = True
                    break
                transitions = tuple((successors[tag], tag) for tag in ("ok", "error"))
            else:
                if (not isinstance(successors, list)
                        or any(not isinstance(target, str) or target not in blocks for target in successors)):
                    malformed = True
                    break
                transitions = tuple((target, None) for target in successors)
            normalized[name] = (tuple(actions), transitions, attempt)
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
            for target, _ in normalized[block_name][1]:
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
            actions, transitions, attempt = normalized[block_name]
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
                    if current not in {"caller", "caller_cleanup_debt"}:
                        findings.append(f"{outcome}:{block_name}:MULTIPLE_CONSUMPTIONS")
                    elif action == "propagate_owned" and not cfg["output_carries_owned"]:
                        findings.append(f"{outcome}:{block_name}:PROPAGATION_DROPS_OWNERSHIP")
                    elif current == "caller_cleanup_debt" and action != "propagate_owned":
                        findings.append(f"{outcome}:{block_name}:CLEANUP_DEBT_NOT_PRESERVED")
                    else:
                        current = ({"release": "released", "transfer": "transferred",
                                    "propagate_owned": "caller_output"}[action]
                                   if current == "caller" else "caller_output_cleanup_debt")
            if attempt:
                if current not in {"caller", "caller_cleanup_debt"}:
                    findings.append(f"{outcome}:{block_name}:RELEASE_WITHOUT_OWNERSHIP")
                    continue
                for target, release_result in transitions:
                    next_state = "released" if release_result == "ok" else "caller_cleanup_debt"
                    before = len(incoming[target])
                    incoming[target].add(next_state)
                    if len(incoming[target]) != before:
                        pending.append(target)
                continue
            if not transitions:
                if current == "caller":
                    findings.append(f"{outcome}:{block_name}:LEAKED_OWNERSHIP")
                elif current == "caller_cleanup_debt":
                    findings.append(f"{outcome}:{block_name}:LEAKED_CLEANUP_DEBT")
                else:
                    terminal_owners.append((outcome, current))
            for target, _ in transitions:
                before = len(incoming[target])
                incoming[target].add(current)
                if len(incoming[target]) != before:
                    pending.append(target)
    return CallCheck("REJECTED" if findings else "ACCEPTED",
                     tuple(sorted(set(findings))), tuple(sorted(terminal_owners)))


def check_owned_call_tree(result_type: Any, outcome_trees: Any) -> CallCheck:
    """Lower a tiny structured ownership tree to CFGs, then check the result.

    The research-only tree grammar is ``{"sequence": [nodes...]}``,
    ``{"if": [then, else]}``,
    ``{"release_attempt": {"ok": node, "error": node}}``, or one action
    string (``release``, ``transfer``, ``propagate_owned``, ``ignore``,
    ``duplicate``, ``use``). Each tagged outcome has ``body`` and
    ``output_carries_owned`` fields. This is not LLMLang syntax; it tests
    whether an explicitly supplied structured body can derive the CFG without
    separately hand-authoring block IDs and edges.
    """
    if not isinstance(outcome_trees, dict) or not outcome_trees:
        return CallCheck("UNKNOWN", ("UNKNOWN_OUTCOME_COVERAGE",), ())
    trees: dict[str, dict[str, Any]] = {}
    valid_actions = {"release", "transfer", "propagate_owned", "ignore", "duplicate", "use"}
    counter = 0

    def fresh() -> str:
        nonlocal counter
        counter += 1
        return f"b{counter}"

    def lower(node: Any, blocks: dict[str, dict[str, Any]], continuation: str | None) -> str:
        if isinstance(node, dict) and set(node) == {"sequence"}:
            items = node["sequence"]
            if not isinstance(items, list):
                raise ValueError("sequence must contain a list")
            current = continuation
            for item in reversed(items):
                current = lower(item, blocks, current)
            if current is None:
                current = fresh()
                blocks[current] = {"actions": [], "successors": []}
            return current
        if isinstance(node, dict) and set(node) == {"if"}:
            arms = node["if"]
            if not isinstance(arms, list) or len(arms) != 2:
                raise ValueError("if requires then and else branches")
            then_entry = lower(arms[0], blocks, continuation)
            else_entry = lower(arms[1], blocks, continuation)
            name = fresh()
            blocks[name] = {"actions": [], "successors": [then_entry, else_entry]}
            return name
        if isinstance(node, dict) and set(node) == {"release_attempt"}:
            arms = node["release_attempt"]
            if not isinstance(arms, dict) or set(arms) != {"ok", "error"}:
                raise ValueError("release_attempt requires ok and error branches")
            ok_entry = lower(arms["ok"], blocks, continuation)
            error_entry = lower(arms["error"], blocks, continuation)
            name = fresh()
            blocks[name] = {"actions": [], "release_attempt": True,
                            "successors": {"ok": ok_entry, "error": error_entry}}
            return name
        if isinstance(node, str) and node in valid_actions:
            name = fresh()
            blocks[name] = {"actions": [node],
                            "successors": [] if continuation is None else [continuation]}
            return name
        raise ValueError("unsupported ownership tree node")

    for outcome, item in outcome_trees.items():
        if (not isinstance(item, dict) or set(item) != {"body", "output_carries_owned"}
                or type(item["output_carries_owned"]) is not bool):
            return CallCheck("UNKNOWN", (f"UNKNOWN_TREE:{outcome}",), ())
        blocks: dict[str, dict[str, Any]] = {}
        try:
            entry = lower(item["body"], blocks, None)
        except ValueError:
            return CallCheck("UNKNOWN", (f"UNKNOWN_TREE:{outcome}",), ())
        trees[outcome] = {"entry": entry, "blocks": blocks,
                          "output_carries_owned": item["output_carries_owned"]}
    return check_owned_call_cfg(result_type, trees)


def execute_owned_call_tree(
    tree: Any,
    *,
    release_results: list[bool],
    branch_choices: list[bool] | None = None,
    output_carries_owned: bool = False,
    owned_on_entry: bool = True,
) -> FlowExecution:
    """Execute one path through the same research tree grammar as the checker.

    ``release_results`` and ``branch_choices`` are explicit environment inputs,
    not nondeterminism hidden by the model. The interpreter is a bounded
    cross-check for the static lowering; it is not LLMLang runtime semantics.
    """
    remaining_releases = list(release_results)
    remaining_branches = list(branch_choices or [])
    events: list[str] = []
    findings: list[str] = []
    if type(owned_on_entry) is not bool or type(output_carries_owned) is not bool:
        return FlowExecution("UNKNOWN", (), "unknown", ("INVALID_OWNERSHIP_INPUT",))
    owner = "caller" if owned_on_entry else "none"

    def evaluate(node: Any) -> None:
        nonlocal owner
        if isinstance(node, dict) and set(node) == {"sequence"}:
            if not isinstance(node["sequence"], list):
                findings.append("INVALID_SEQUENCE")
                return
            for item in node["sequence"]:
                evaluate(item)
            return
        if isinstance(node, dict) and set(node) == {"if"}:
            arms = node["if"]
            if not isinstance(arms, list) or len(arms) != 2 or not remaining_branches:
                findings.append("MISSING_OR_INVALID_BRANCH_INPUT")
                return
            evaluate(arms[0] if remaining_branches.pop(0) else arms[1])
            return
        if isinstance(node, dict) and set(node) == {"release_attempt"}:
            arms = node["release_attempt"]
            if (not isinstance(arms, dict) or set(arms) != {"ok", "error"}
                    or not remaining_releases):
                findings.append("MISSING_OR_INVALID_RELEASE_RESULT")
                return
            succeeded = remaining_releases.pop(0)
            if type(succeeded) is not bool:
                findings.append("INVALID_RELEASE_RESULT")
                return
            if owner not in {"caller", "caller_cleanup_debt"}:
                findings.append("RELEASE_WITHOUT_OWNERSHIP")
                return
            events.append("release:ok" if succeeded else "release:error")
            owner = "released" if succeeded else "caller_cleanup_debt"
            evaluate(arms["ok"] if succeeded else arms["error"])
            return
        if not isinstance(node, str) or node not in {
            "release", "transfer", "propagate_owned", "ignore", "duplicate", "use"
        }:
            findings.append("UNSUPPORTED_TREE_NODE")
            return
        if owner == "none":
            findings.append("ACTION_WITHOUT_OWNED_VALUE")
            return
        if owner == "caller_cleanup_debt" and node not in {"propagate_owned"}:
            findings.append("CLEANUP_DEBT_NOT_PRESERVED")
            return
        if node == "use":
            if owner != "caller":
                findings.append("USE_AFTER_MOVE")
            else:
                events.append("use")
        elif node == "release":
            if owner != "caller":
                findings.append("RELEASE_WITHOUT_OWNERSHIP")
            else:
                owner = "released"
                events.append("release:assumed_ok")
        elif node == "transfer":
            if owner != "caller":
                findings.append("TRANSFER_WITHOUT_OWNERSHIP")
            else:
                owner = "transferred"
                events.append("transfer")
        elif node == "propagate_owned":
            if owner not in {"caller", "caller_cleanup_debt"}:
                findings.append("PROPAGATE_WITHOUT_OWNERSHIP")
            elif not output_carries_owned:
                findings.append("PROPAGATION_DROPS_OWNERSHIP")
            else:
                owner = "caller_output_cleanup_debt" if owner == "caller_cleanup_debt" else "caller_output"
                events.append("propagate_owned")
        elif node == "ignore":
            findings.append("IGNORED_OWNERSHIP")
        else:
            findings.append("DUPLICATE_OWNER")

    evaluate(tree)
    if owner in {"caller", "caller_cleanup_debt"} and not findings:
        findings.append("LEAKED_CLEANUP_DEBT" if owner == "caller_cleanup_debt" else "LEAKED_OWNERSHIP")
    return FlowExecution("REJECTED" if findings else "ACCEPTED", tuple(events), owner,
                         tuple(sorted(set(findings))))
