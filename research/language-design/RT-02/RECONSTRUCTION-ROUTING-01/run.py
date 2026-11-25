"""Compare independent validation and checked fallback on seeded untrusted drafts."""

import hashlib
import importlib.util
import json
from pathlib import Path
import platform

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ROUNDTRIP = HERE.parent / "RECONSTRUCTION-ROUNDTRIP-01"
DIRECTION = HERE.parent / "SEMANTIC-DIRECTION-01/run.py"
SPEC = importlib.util.spec_from_file_location("direction_study", DIRECTION)
DIRECTION_STUDY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DIRECTION_STUDY)
FIXTURE = DIRECTION_STUDY.FIXTURE

DRAFT_DEFECTS = {"unreadable-draft", "draft-changes-typed-meaning"}


def inspect_draft(corpus, typed, text):
    decoded = FIXTURE.decode(text) if text is not None else None
    if decoded is None:
        return "unreadable-draft"
    candidate = {c["id"]: c for c in FIXTURE.semantic_payload(typed)}
    if candidate != decoded:
        return "draft-changes-typed-meaning"
    if FIXTURE.source_problems(corpus, typed):
        return "unresolved-provenance"
    baseline = {c["id"]: c for c in corpus["clauses"]}
    outcome = DIRECTION_STUDY.compare(baseline, decoded, FIXTURE.TRACES)
    return ("eligible-for-review" if outcome["direction"] == "EQUIVALENT_IN_DOMAIN"
            else "candidate-differs-from-source")


def deterministic(corpus, typed):
    rendered = FIXTURE.reconstruct(typed)
    if rendered["status"] != "RECONSTRUCTED":
        return "unsupported-rendering"
    return inspect_draft(corpus, typed, rendered["lines"])


def assess(corpus, typed, proposed):
    decoded = FIXTURE.decode(proposed) if proposed is not None else None
    drafted = inspect_draft(corpus, typed, proposed)
    checked_deterministic = deterministic(corpus, typed)
    fallback = drafted in DRAFT_DEFECTS
    return {"parse_only_accepts": decoded is not None,
            "deterministic_checked": checked_deterministic,
            "independent_check": drafted,
            "hybrid_fallback_used": fallback,
            "hybrid_checked": checked_deterministic if fallback else drafted,
            "seeded_draft": proposed}


def main():
    corpus_path = ROUNDTRIP / "corpus.json"
    corpus = json.loads(corpus_path.read_text())
    baseline = corpus["clauses"]
    good = FIXTURE.reconstruct(baseline)["lines"]
    changed_semantics = FIXTURE.changed(baseline, "deadline", deadline=7)
    changed_text = FIXTURE.reconstruct(changed_semantics)["lines"]
    scenarios = {
        "faithful": (baseline, good),
        "formatting_only": (baseline, [" ".join(line.split()) + " " for line in good]),
        "incorrect_deadline": (baseline, changed_text),
        "omitted_exception": (baseline, good[:1]),
        "added_action": (baseline, [*good, good[0].replace("[deadline]", "[extra]")
                                     .replace("confirmation", "notification")]),
        "malformed_output": (baseline, [good[0].replace(", inclusive", ""), good[1]]),
        "missing_output": (baseline, None),
        "faithful_to_wrong_formal_input": (changed_semantics, changed_text),
        "unresolved_provenance": (FIXTURE.changed(baseline, "deadline", refs=["intent", "operator", "missing"]),
                                  good),
        "unsupported_formal_with_readable_draft": (FIXTURE.changed(baseline, "deadline", action="webhook"), good),
    }
    results = {key: assess(corpus, *scenario) for key, scenario in scenarios.items()}
    eligible = "eligible-for-review"
    assert {k for k, value in results.items() if value["independent_check"] == eligible} == {
        "faithful", "formatting_only"
    }
    assert {k for k, value in results.items() if value["hybrid_checked"] == eligible} == {
        "faithful", "formatting_only", "incorrect_deadline", "omitted_exception",
        "added_action", "malformed_output", "missing_output"
    }
    assert {k for k, value in results.items() if value["parse_only_accepts"] and
            value["independent_check"] != eligible} == {
        "incorrect_deadline", "omitted_exception", "added_action",
        "faithful_to_wrong_formal_input", "unresolved_provenance", "unsupported_formal_with_readable_draft"
    }
    assert not results["faithful_to_wrong_formal_input"]["hybrid_fallback_used"]
    assert not results["unresolved_provenance"]["hybrid_fallback_used"]
    assert results["unsupported_formal_with_readable_draft"]["hybrid_checked"] == "unsupported-rendering"
    paths = (Path(__file__), DIRECTION, ROUNDTRIP / "run.py", ROUNDTRIP / "render.py", corpus_path)
    return {
        "schema": "llmlang-rt02-reconstruction-routing/1", "python": platform.python_version(),
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        "proposal_artifact_type": "seeded-drafts", "real_model_measurements": False, "cases": results,
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
