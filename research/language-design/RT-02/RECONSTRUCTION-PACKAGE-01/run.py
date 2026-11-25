"""Construct seven review artifact roles for the bounded RT-02 fixture."""

import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DIRECTION = HERE.parent / "SEMANTIC-DIRECTION-01/run.py"
ROUNDTRIP = HERE.parent / "RECONSTRUCTION-ROUNDTRIP-01"
SPEC = importlib.util.spec_from_file_location("direction_study", DIRECTION)
DIRECTION_STUDY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DIRECTION_STUDY)
FIXTURE = DIRECTION_STUDY.FIXTURE
PROTOTYPE = ROOT / "research/PROTOTYPES/DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))
from src.semantic_graph import digest

ROLES = ("contract_text", "business_rules", "scenarios", "counterexamples", "semantic_differences",
         "unresolved_questions", "provenance")


def scenario_rows(model):
    cases = (
        ("satisfying", ("retail", "succeeded", 4, None)),
        ("late", ("retail", "succeeded", 8, None)),
        ("exception", ("retail", "failed", 3, None)),
        ("incomplete_observation", ("retail", None, None, None)),
    )
    rows = []
    for name, trace in cases:
        windows = []
        if trace[1] is None:
            outcome = "UNKNOWN"
            explanation = "Reservation outcome has not been observed."
        else:
            matching = [ident for ident, clause in model.items()
                        if clause["scope"] in {trace[0], "all"} and clause["condition"] == trace[1]]
            for ident in matching:
                clause = model[ident]
                start = 2 if clause["origin"] == "reservation observation" else 0
                end = FIXTURE.HORIZON if clause["deadline"] is None else start + clause["deadline"]
                windows.append({"clause": ident, "start": start, "end_inclusive": end})
            outcome = "SATISFIES" if FIXTURE.allows(model, trace) else "VIOLATES"
            explanation = "Applicable rules: " + ", ".join(matching) if matching else "No applicable rule."
        rows.append({"name": name, "trace": FIXTURE.trace_payload(trace),
                     "outcome": outcome, "explanation": explanation, "applicable_windows_s": windows})
    return rows


def provenance_rows(corpus, clauses):
    sources = corpus["source_fragments"]
    return {
        c["id"]: [
            {"fragment": ref,
             "authorized_in_fixture": ref in corpus["authorized_fragments"],
             "source_identity": digest({"type": "rt02-source-fragment", "text": sources[ref]})
             if ref in sources else None}
            for ref in c["refs"]
        ]
        for c in clauses
    }


def build_package(corpus, clauses, *, altered_text=False):
    formal = {clause["id"]: clause for clause in FIXTURE.semantic_payload(clauses)}
    outputs = dict.fromkeys(ROLES)
    lines = FIXTURE.reconstruct(clauses)
    problems = FIXTURE.source_problems(corpus, clauses)
    outputs["provenance"] = provenance_rows(corpus, clauses)
    outputs["unresolved_questions"] = [
        {"kind": "provenance-gap", "clause": clause, "detail": gaps} for clause, gaps in problems.items()
    ]
    if lines["status"] != "RECONSTRUCTED":
        outputs["unresolved_questions"].append({"kind": "unsupported-formal-model", "detail": lines["reason"]})
        status = "UNKNOWN"
    else:
        text = lines["lines"]
        if altered_text:
            text[0] = text[0].replace("5 seconds", "7 seconds")
        outputs["contract_text"] = text
        outputs["business_rules"] = list(formal.values())
        outputs["scenarios"] = scenario_rows(formal)
        baseline = {c["id"]: c for c in corpus["clauses"]}
        differences = DIRECTION_STUDY.compare(baseline, formal, FIXTURE.TRACES)
        outputs["semantic_differences"] = differences
        outputs["counterexamples"] = [
            {"kind": key, "trace": differences[key + "_witness"]}
            for key in ("candidate_only", "source_only") if differences[key + "_witness"] is not None
        ]
        outputs["counterexamples"].extend(
            {"kind": "candidate_scenario_violation", "name": row["name"], "trace": row["trace"]}
            for row in outputs["scenarios"] if row["outcome"] == "VIOLATES"
        )
        decoded = FIXTURE.decode(text)
        if decoded != formal:
            outputs["unresolved_questions"].append(
                {"kind": "reconstruction-mismatch", "detail": "Text has a different typed reading.",
                 "typed_delta": DIRECTION_STUDY.changes(formal, decoded) if decoded is not None else None}
            )
            status = "NEEDS_REVISION"
        elif differences["direction"] != "EQUIVALENT_IN_DOMAIN":
            status = "NEEDS_REVISION"
        else:
            status = "UNKNOWN" if problems else "ELIGIBLE_FOR_REVIEW"
    review_payload = {
        "schema": "llmlang-rt02-reconstruction-package/1",
        "formal_identity": digest({"type": "rt02-formal-input", "clauses": formal}),
        "status": status,
        "outputs": outputs,
    }
    return review_payload | {"package_identity": digest(review_payload)}


def main():
    corpus_path = ROUNDTRIP / "corpus.json"
    corpus = json.loads(corpus_path.read_text())
    clauses = corpus["clauses"]
    cases = {
        "original": build_package(corpus, clauses),
        "shifted_clock": build_package(corpus, FIXTURE.changed(clauses, "deadline", origin="reservation observation")),
        "dangling_source": build_package(corpus, FIXTURE.changed(clauses, "deadline",
                                                                 refs=["intent", "operator", "missing"])),
        "unsupported_action": build_package(corpus, FIXTURE.changed(clauses, "deadline", action="webhook")),
        "altered_rendering": build_package(corpus, clauses, altered_text=True),
    }
    assert [c["status"] for c in cases.values()] == [
        "ELIGIBLE_FOR_REVIEW", "NEEDS_REVISION", "UNKNOWN", "UNKNOWN", "NEEDS_REVISION"
    ]
    assert len({c["package_identity"] for c in cases.values()}) == 5
    assert cases["original"]["formal_identity"] == cases["altered_rendering"]["formal_identity"]
    assert cases["original"]["formal_identity"] == cases["dangling_source"]["formal_identity"]
    assert {row["kind"] for row in cases["shifted_clock"]["outputs"]["counterexamples"]} == {
        "candidate_only", "source_only", "candidate_scenario_violation"
    }
    assert cases["unsupported_action"]["outputs"]["contract_text"] is None
    assert cases["unsupported_action"]["outputs"]["semantic_differences"] is None
    assert cases["original"]["outputs"]["scenarios"][-1]["outcome"] == "UNKNOWN"
    paths = (Path(__file__), DIRECTION, ROUNDTRIP / "run.py", ROUNDTRIP / "render.py", corpus_path,
             PROTOTYPE / "src/semantic_graph.py")
    return {"python": platform.python_version(),
            "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            "cases": cases}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
