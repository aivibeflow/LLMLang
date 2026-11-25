"""Check typed function descriptions, derived retrieval identities and query provenance."""

from dataclasses import asdict, dataclass
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform


DESCRIPTION = {
    "schema": "rt35-description/v1",
    "intent": {"domain": "reservations", "operation": "allocate-within-limit"},
    "inputs": [{"role": "requested-quantity", "type": "u32", "ownership": "copy"}],
    "outputs": [{"role": "reserved-quantity", "type": "u32", "ownership": "caller"}],
    "preconditions": [{"predicate": "positive", "role": "requested-quantity"}],
    "postconditions": [{"predicate": "bounded-by-request", "role": "reserved-quantity"}],
    "effects": ["ledger-write"],
    "capabilities": ["reservation-ledger"],
    "errors": [{"tag": "Unavailable", "state": "unchanged", "retry": "permitted"}],
    "constraints": {"maximum-request": 100, "ordering": "request-order"},
    "cost": {"state": "unknown"},
}
EXACT = {"body": ["reserve", "checked"], "contract": "fixture-contract:1", "profile": "fixture-target"}
HARD_SOURCES = {"signed-requirement", "reviewed-query-field"}
FORMS = ("intent", "structured", "hybrid")


def digest(domain, value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256(domain.encode() + b"\0" + payload).hexdigest()


@dataclass(frozen=True)
class Clause:
    field: str
    relation: str
    rhs: str
    strength: str
    source: str
    request_scope: str


def project(description, method):
    values = {"purpose": description["intent"], "types": [description["inputs"], description["outputs"]],
              "effects": description["effects"]}
    return digest("derived-fingerprint", {"version": method, "features": values})


def index_key(snapshot, fingerprint, layout):
    return digest("rebuildable-index", [snapshot, fingerprint, layout])


def query(form, intent, constraints, scope):
    if form not in FORMS or any(row.strength not in ("soft", "hard") for row in constraints):
        return None
    if (form == "intent" and (not intent or constraints)
            or form == "structured" and (intent or not constraints)
            or form == "hybrid" and (not intent or not constraints)):
        return None
    if any(row.strength == "hard" and (row.source not in HARD_SOURCES or row.request_scope != scope)
           for row in constraints):
        return None
    return {"form": form, "intent": intent, "candidate_selection_only": form == "intent",
            "hard": [asdict(row) for row in constraints if row.strength == "hard"],
            "soft": [asdict(row) for row in constraints if row.strength == "soft"],
            "scope": scope}


def run():
    exact = digest("fixture-function", EXACT)
    semantic = digest("canonical-description", DESCRIPTION)
    fp_a, fp_b = (project(DESCRIPTION, rev) for rev in ("lexical:1", "aspects:2"))
    assert fp_a != fp_b
    assert fp_a == project({**DESCRIPTION, "cost": {"state": "observed", "units": "ns", "median": 12}}, "lexical:1")
    assert semantic != digest("canonical-description", {**DESCRIPTION, "cost": {"state": "observed"}})
    assert index_key("snapshot-a", fp_a, "table:v1") != index_key("snapshot-a", fp_a, "table:v2")
    assert index_key("snapshot-a", fp_a, "table:v1") != index_key("snapshot-b", fp_a, "table:v1")
    assert exact == digest("fixture-function", EXACT)

    accepted = 0
    checks = 0
    for form, text, strength, source, scope in product(
        FORMS, ("", "allocate with no IO"), ("absent", "soft", "hard"),
        ("signed-requirement", "reviewed-query-field", "free-prose"), ("current", "stale")
    ):
        clauses = () if strength == "absent" else (Clause("effects", "subset", "none", strength, source, scope),)
        observed = query(form, text, clauses, "current")
        correct_shape = (form, bool(text), bool(clauses)) in {
            ("intent", True, False), ("structured", False, True), ("hybrid", True, True)
        }
        correct_provenance = not clauses or strength != "hard" or (scope == "current" and source in HARD_SOURCES)
        assert (observed is not None) == (correct_shape and correct_provenance)
        if observed is not None:
            assert len(observed["hard"]) == int(bool(clauses) and strength == "hard")
            accepted += 1
        checks += 1

    free_text = query("intent", "must avoid ledger writes", (), "current")
    assert free_text["candidate_selection_only"] and free_text["hard"] == []
    unknown_strength = Clause("effects", "subset", "none", "unknown", "reviewed-query-field", "current")
    assert query("structured", "", (unknown_strength,), "current") is None
    assert query("unsupported-form", "allocate", (), "current") is None
    return {"python": platform.python_version(), "description": DESCRIPTION, "exact_function_address": exact,
            "description_digest": semantic, "fingerprint_versions": [fp_a, fp_b],
            "checks": checks, "accepted": accepted, "refused": checks - accepted,
            "intent_prose_cannot_form_hard_requirement": True,
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
