"""Evaluate exact clarification overrides on a closed scope population."""

from dataclasses import asdict, replace
import hashlib
import importlib.util
from itertools import product
import json
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PROVENANCE = HERE.parent / "CLAUSE-PROVENANCE-01/run.py"
SPEC = importlib.util.spec_from_file_location("base_provenance", PROVENANCE)
BASE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BASE
SPEC.loader.exec_module(BASE)

CONTEXTS = tuple(product(("retail", "wholesale"), ("succeeded", "failed")))
SCOPES = {
    "all-success": {(tier, outcome) for tier, outcome in CONTEXTS if outcome == "succeeded"},
    "retail-success": {("retail", "succeeded")},
    "all-failure": {(tier, outcome) for tier, outcome in CONTEXTS if outcome == "failed"},
    "all": set(CONTEXTS),
}


def select(sources, interpretations):
    """Return dispositions and supporting exact attestations for each obligation cell."""
    index = {record.identity: record for record in interpretations}
    defects = {}
    for identity, record in index.items():
        problem = BASE.source_problem(sources, record)
        if record.scope not in SCOPES:
            problem = problem or "UNKNOWN_SCOPE"
        if not problem and record.supersedes:
            parent = index.get(record.supersedes)
            if (parent is None or parent.scope not in SCOPES or parent.field != record.field
                    or not SCOPES[record.scope] <= SCOPES[parent.scope]):
                problem = "INVALID_OVERRIDE"
        if problem:
            defects[identity] = problem
    if defects:
        return {"status": "UNKNOWN_EVIDENCE", "defects": defects, "cells": {}}

    cells = {}
    for tier, outcome in CONTEXTS:
        field = "deadline" if outcome == "succeeded" else "automatic-confirmation"
        applicable = {key: r for key, r in index.items()
                      if r.field == field and (tier, outcome) in SCOPES[r.scope]}
        replaced = {r.supersedes for r in applicable.values() if r.supersedes}
        current = {key: r for key, r in applicable.items() if key not in replaced}
        alternatives = sorted({r.value for r in current.values()})
        status = {0: "UNCOVERED", 1: "GROUNDED"}.get(len(alternatives), "CONFLICT")
        cells[f"{tier}/{outcome}"] = {"status": status, "alternatives": alternatives,
                                    "current_support": sorted(current), "replaced_in_scope": sorted(replaced)}
    resolved = all(row["status"] == "GROUNDED" for row in cells.values())
    return {"status": "GROUNDED" if resolved else "UNKNOWN_EVIDENCE", "defects": {}, "cells": cells}


def main():
    sources = {
        "default": "Require confirmation within five seconds for every order with a successful reservation.",
        "retail": "For successful retail reservations, use seven seconds.",
        "prohibition": "Do not auto-confirm any order whose reservation failed.",
    }
    default = replace(BASE.interpret(sources, "default", "within five seconds", "deadline", "5"),
                      scope="all-success")
    retail = replace(BASE.interpret(sources, "retail", "use seven seconds", "deadline", "7"),
                     scope="retail-success")
    prohibition = replace(BASE.interpret(sources, "prohibition", "Do not auto-confirm",
                                         "automatic-confirmation", "forbidden"),
                          scope="all-failure")
    override = replace(retail, supersedes=default.identity)
    expanded_override = replace(override, scope="all")
    invalid_authority = replace(override, authority="proposal-agent")
    unrecognized_scope = replace(retail, scope="international")
    stale_sources = sources | {"retail": sources["retail"] + " Edited."}
    cases = {
        "complete_default": (sources, (default, prohibition), "GROUNDED"),
        "implicit_narrower_rule": (sources, (default, retail, prohibition), "UNKNOWN_EVIDENCE"),
        "exact_local_override": (sources, (default, override, prohibition), "GROUNDED"),
        "override_exceeds_parent_scope": (sources, (default, expanded_override, prohibition), "UNKNOWN_EVIDENCE"),
        "uncovered_wholesale": (sources, (retail, prohibition), "UNKNOWN_EVIDENCE"),
        "stale_override_source": (stale_sources, (default, override, prohibition), "UNKNOWN_EVIDENCE"),
        "unauthorized_override": (sources, (default, invalid_authority, prohibition), "UNKNOWN_EVIDENCE"),
        "unknown_scope": (sources, (default, unrecognized_scope, prohibition), "UNKNOWN_EVIDENCE"),
        "override_missing_exact_parent": (sources, (override, prohibition), "UNKNOWN_EVIDENCE"),
    }
    results = {}
    for label, (selected_sources, interpretations, expected) in cases.items():
        result = select(selected_sources, interpretations)
        assert result["status"] == expected
        results[label] = result | {"selected": [item.identity for item in interpretations]}
    ordinary = results["implicit_narrower_rule"]["cells"]
    assert ordinary["retail/succeeded"]["status"] == "CONFLICT"
    assert ordinary["wholesale/succeeded"]["alternatives"] == ["5"]
    assert ordinary["retail/failed"]["alternatives"] == ["forbidden"]
    scoped = results["exact_local_override"]["cells"]
    assert scoped["retail/succeeded"]["alternatives"] == ["7"]
    assert scoped["retail/succeeded"]["replaced_in_scope"] == [default.identity]
    assert scoped["wholesale/succeeded"]["alternatives"] == ["5"]
    assert not scoped["wholesale/succeeded"]["replaced_in_scope"]
    assert results["uncovered_wholesale"]["cells"]["wholesale/succeeded"]["status"] == "UNCOVERED"
    expected_defects = {
        "override_exceeds_parent_scope": "INVALID_OVERRIDE",
        "stale_override_source": "STALE_SOURCE_REVISION",
        "unauthorized_override": "UNAUTHORIZED",
        "unknown_scope": "UNKNOWN_SCOPE",
        "override_missing_exact_parent": "INVALID_OVERRIDE",
    }
    for label, reason in expected_defects.items():
        assert list(results[label]["defects"].values()) == [reason]
    paths = (Path(__file__), PROVENANCE, BASE.PROTOTYPE / "src/semantic_graph.py")
    interpretations = (default, retail, prohibition, override, expanded_override,
                       invalid_authority, unrecognized_scope)
    return {
        "schema": "llmlang-rt02-scoped-provenance/1", "python": platform.python_version(),
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        "sources": sources, "contexts": CONTEXTS,
        "interpretations": {row.identity: asdict(row) for row in interpretations},
        "cases": results,
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
