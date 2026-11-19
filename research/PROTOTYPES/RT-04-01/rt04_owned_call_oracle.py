"""Table-driven path oracle for the COR-13 owned-call tree experiment.

This file intentionally does not import the checker or tree interpreter. It
is a small executable statement of the one-handle path rules used to compare
their finite traces; it is not a source-language semantics or an independent
human review.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OracleTrace:
    status: str
    events: tuple[str, ...]
    owner: str
    findings: tuple[str, ...] = ()


# Rows are (input owner, action) -> (next owner, event, finding). Keeping the
# transition relation explicit makes expected paths inspectable without using
# the production prototype's evaluator.
_ACTIONS = {
    ("caller", "use"): ("caller", "use", None),
    ("caller", "release"): ("released", "release:assumed_ok", None),
    ("caller", "transfer"): ("transferred", "transfer", None),
    ("caller", "propagate_owned"): ("caller_output", "propagate_owned", None),
    ("caller_cleanup_debt", "propagate_owned"):
        ("caller_output_cleanup_debt", "propagate_owned", None),
}


def run_oracle(
    tree: Any,
    *,
    release_results: list[bool],
    branch_choices: list[bool] | None = None,
    output_carries_owned: bool = False,
    owned_on_entry: bool = True,
) -> OracleTrace:
    """Evaluate one explicit path using the oracle transition table."""
    if type(owned_on_entry) is not bool or type(output_carries_owned) is not bool:
        return OracleTrace("UNKNOWN", (), "unknown", ("INVALID_OWNERSHIP_INPUT",))

    owner = "caller" if owned_on_entry else "none"
    releases = iter(release_results)
    branches = iter(branch_choices or [])
    events: list[str] = []
    findings: list[str] = []

    def visit(node: Any) -> None:
        nonlocal owner
        if isinstance(node, dict) and set(node) == {"sequence"}:
            if not isinstance(node["sequence"], list):
                findings.append("INVALID_SEQUENCE")
                return
            for child in node["sequence"]:
                visit(child)
            return
        if isinstance(node, dict) and set(node) == {"if"}:
            arms = node["if"]
            if not isinstance(arms, list) or len(arms) != 2:
                findings.append("MISSING_OR_INVALID_BRANCH_INPUT")
                return
            selected = next(branches, None)
            if type(selected) is not bool:
                findings.append("MISSING_OR_INVALID_BRANCH_INPUT")
                return
            visit(arms[0] if selected else arms[1])
            return
        if isinstance(node, dict) and set(node) == {"release_attempt"}:
            arms = node["release_attempt"]
            if not isinstance(arms, dict) or set(arms) != {"ok", "error"}:
                findings.append("MISSING_OR_INVALID_RELEASE_RESULT")
                return
            succeeded = next(releases, None)
            if type(succeeded) is not bool:
                findings.append("MISSING_OR_INVALID_RELEASE_RESULT")
                return
            if owner not in {"caller", "caller_cleanup_debt"}:
                findings.append("RELEASE_WITHOUT_OWNERSHIP")
                return
            owner = "released" if succeeded else "caller_cleanup_debt"
            events.append("release:ok" if succeeded else "release:error")
            visit(arms["ok"] if succeeded else arms["error"])
            return

        if not isinstance(node, str) or node not in {
            "use", "release", "transfer", "propagate_owned", "ignore", "duplicate"
        }:
            findings.append("UNSUPPORTED_TREE_NODE")
            return
        if owner == "none":
            findings.append("ACTION_WITHOUT_OWNED_VALUE")
            return
        if owner == "caller_cleanup_debt" and node != "propagate_owned":
            findings.append("CLEANUP_DEBT_NOT_PRESERVED")
            return
        if node == "ignore":
            findings.append("IGNORED_OWNERSHIP")
            return
        if node == "duplicate":
            findings.append("DUPLICATE_OWNER")
            return
        if node == "use" and owner != "caller":
            findings.append("USE_AFTER_MOVE")
            return
        if (node == "propagate_owned" and owner in {"caller", "caller_cleanup_debt"}
                and not output_carries_owned):
            findings.append("PROPAGATION_DROPS_OWNERSHIP")
            return
        transition = _ACTIONS.get((owner, node))
        if transition is None:
            failures = {
                "release": "RELEASE_WITHOUT_OWNERSHIP",
                "transfer": "TRANSFER_WITHOUT_OWNERSHIP",
                "propagate_owned": "PROPAGATE_WITHOUT_OWNERSHIP",
            }
            findings.append(failures.get(node, "INVALID_OWNERSHIP_TRANSITION"))
            return
        owner, event, finding = transition
        if event is not None:
            events.append(event)
        if finding is not None:
            findings.append(finding)

    visit(tree)
    if owner in {"caller", "caller_cleanup_debt"} and not findings:
        findings.append("LEAKED_CLEANUP_DEBT" if owner == "caller_cleanup_debt" else "LEAKED_OWNERSHIP")
    return OracleTrace("REJECTED" if findings else "ACCEPTED", tuple(events), owner,
                       tuple(sorted(set(findings))))
