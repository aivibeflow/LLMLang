"""Classify requirement differences within an explicitly finite trace domain."""

import hashlib
import importlib.util
import json
from pathlib import Path
import platform

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ROUNDTRIP = HERE.parent / "RECONSTRUCTION-ROUNDTRIP-01"
SPEC = importlib.util.spec_from_file_location("trace_fixture", ROUNDTRIP / "run.py")
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)
FIELDS = ("scope", "condition", "mode", "action", "origin", "deadline")


def direction(gained, lost, *, complete):
    if gained and lost:
        return "INCOMPARABLE"
    if not complete:
        return "UNKNOWN_DIRECTION"
    if gained:
        return "WEAKENED"
    if lost:
        return "STRENGTHENED"
    return "EQUIVALENT_IN_DOMAIN"


def changes(baseline, candidate):
    return {
        "removed_clause_ids": sorted(baseline.keys() - candidate.keys()),
        "added_clause_ids": sorted(candidate.keys() - baseline.keys()),
        "changed_fields": {
            key: [field for field in FIELDS if baseline[key][field] != candidate[key][field]]
            for key in sorted(baseline.keys() & candidate.keys())
            if any(baseline[key][field] != candidate[key][field] for field in FIELDS)
        },
    }


def compare(baseline, candidate, traces):
    source_allowed = {trace for trace in traces if FIXTURE.independently_expected(trace)}
    candidate_allowed = {trace for trace in traces if FIXTURE.allows(candidate, trace)}
    gained = candidate_allowed - source_allowed
    lost = source_allowed - candidate_allowed
    first_gained = next((FIXTURE.trace_payload(t) for t in traces if t in gained), None)
    first_lost = next((FIXTURE.trace_payload(t) for t in traces if t in lost), None)
    emptied_contexts = sorted({trace[:2] for trace in source_allowed} - {trace[:2] for trace in candidate_allowed})
    return {
        "traces": len(traces), "source_allowed": len(source_allowed), "candidate_allowed": len(candidate_allowed),
        "candidate_only": len(gained), "source_only": len(lost),
        "direction": direction(gained, lost, complete=set(traces) == set(FIXTURE.TRACES)),
        "candidate_only_witness": first_gained, "source_only_witness": first_lost,
        "emptied_observed_contexts": emptied_contexts,
        "typed_delta": changes(baseline, candidate),
    }


def main():
    original = json.loads((ROUNDTRIP / "corpus.json").read_text())["clauses"]
    baseline = {clause["id"]: clause for clause in original}
    deadline = baseline["deadline"]
    exception = baseline["exception"]
    all_traces = FIXTURE.TRACES
    assert len(all_traces) == len(set(all_traces)) == 484
    assert all(FIXTURE.allows(baseline, t) == FIXTURE.independently_expected(t) for t in all_traces)
    cases = {
        "original": (baseline, 0, 0),
        "omitted_exception": ({"deadline": deadline}, 110, 0),
        "added_notification": (baseline | {"notification": deadline | {"id": "notification", "action": "notification"}},
                               0, 30),
        "longer_deadline": (baseline | {"deadline": deadline | {"deadline": 7}}, 22, 0),
        "shorter_deadline": (baseline | {"deadline": deadline | {"deadline": 3}}, 0, 22),
        "flipped_exception": (baseline | {"exception": exception | {"mode": "require"}}, 110, 11),
        "shifted_origin": (baseline | {"deadline": deadline | {"origin": "reservation observation"}}, 22, 22),
        "expanded_scope": (baseline | {"deadline": deadline | {"scope": "all"}}, 0, 55),
        "shifted_scope": (baseline | {"deadline": deadline | {"scope": "wholesale"}}, 55, 55),
        "shifted_condition": (baseline | {"deadline": deadline | {"condition": "failed"}}, 55, 11),
        "redundant_addition": (baseline | {"copy": deadline | {"id": "copy"}}, 0, 0),
        "contradictory_addition": (baseline | {"forbid": deadline | {"id": "forbid", "mode": "forbid"}}, 0, 66),
    }
    observations = {}
    for name, (candidate, gained, lost) in cases.items():
        row = compare(baseline, candidate, all_traces)
        assert (row["candidate_only"], row["source_only"]) == (gained, lost), (name, row)
        observations[name] = row
    assert observations["contradictory_addition"]["emptied_observed_contexts"] == [("retail", "succeeded")]

    limited = tuple(t for t in all_traces if t[2] is None or t[2] <= 5)
    truncated = compare(baseline, cases["longer_deadline"][0], limited)
    assert truncated["direction"] == "UNKNOWN_DIRECTION" and truncated["candidate_only"] == 0
    one_sided = tuple(t for t in all_traces if t[2] is None or t[2] >= 2)
    limited_shift = compare(baseline, cases["shifted_origin"][0], one_sided)
    assert limited_shift["candidate_only"] == 22 and limited_shift["source_only"] == 0
    assert limited_shift["direction"] == "UNKNOWN_DIRECTION"
    paths = (Path(__file__), ROUNDTRIP / "run.py", ROUNDTRIP / "corpus.json")
    return {
        "schema": "llmlang-rt02-semantic-direction/1", "python": platform.python_version(),
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        "complete_domain_cases": observations,
        "incomplete_domain_cases": {"hidden_difference": truncated, "hidden_reverse_witness": limited_shift},
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
