"""Check hard compatibility, explicit unknown results and snapshot ambiguity."""

from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform


@dataclass(frozen=True)
class Profile:
    types: tuple[str, str]
    ownership: str
    admitted_inputs: frozenset
    result_values: frozenset
    effects: frozenset
    capabilities: frozenset
    failures: frozenset


QUERY = Profile(("u32", "u32"), "borrowed", frozenset((1, 2, 3)), frozenset((0, 1, 2, 3)),
                frozenset(("read",)), frozenset(("ledger-reader",)), frozenset(("unchanged-on-error",)))
GOOD = Profile(("u32", "u32"), "borrowed", frozenset((0, 1, 2, 3)), frozenset((0, 1)),
               frozenset(("read",)), frozenset(("ledger-reader",)), frozenset(("unchanged-on-error",)))
FACETS = ("types", "ownership", "preconditions", "postconditions", "effects", "capabilities", "failure")


def direct_facts(query, provider):
    return dict(zip(FACETS, (
        provider.types == query.types,
        provider.ownership == query.ownership,
        query.admitted_inputs <= provider.admitted_inputs,
        provider.result_values <= query.result_values,
        provider.effects <= query.effects,
        provider.capabilities <= query.capabilities,
        provider.failures <= query.failures,
    ), strict=True))


def assess(facts):
    regressions = sorted(facet for facet in FACETS if facts.get(facet) is False)
    unknown = sorted(facet for facet in FACETS if facts.get(facet) is None)
    if regressions:
        return "excluded", regressions
    if unknown:
        return "unknown", unknown
    return "compatible", []


def decide(inventory_complete, candidates):
    # Similarity ranks suggestions only. Only checked facts and exact inventory decide binding.
    ranked = sorted(candidates, key=lambda row: (-row[1], row[0]))
    reports = {}
    for identity, _, facts in ranked:
        reports.setdefault(identity, set()).add(assess(facts)[0])
    known = sorted(identity for identity, verdicts in reports.items() if verdicts == {"compatible"})
    unknown = sorted(identity for identity, verdicts in reports.items()
                     if len(verdicts) != 1 or "unknown" in verdicts)
    if len(known) > 1:
        return "ambiguous", known
    if unknown or not inventory_complete:
        return "pending", unknown
    return ("bound", known) if known else ("no-match", [])


def run():
    counts = Counter()
    for choices in product((True, False, None), repeat=len(FACETS)):
        facts = dict(zip(FACETS, choices, strict=True))
        observed, reasons = assess(facts)
        expected = "excluded" if False in choices else "unknown" if None in choices else "compatible"
        assert observed == expected
        assert reasons == sorted(name for name, verdict in facts.items()
                                 if (verdict is False if expected == "excluded" else verdict is None))
        counts[observed] += 1
    changes = {
        "types": {"types": ("u64", "u32")},
        "ownership": {"ownership": "consumed"},
        "preconditions": {"admitted_inputs": frozenset((1, 2))},
        "postconditions": {"result_values": frozenset((1, 7))},
        "effects": {"effects": frozenset(("write",))},
        "capabilities": {"capabilities": frozenset(("counter-admin",))},
        "failure": {"failures": frozenset(("partial-write-on-error",))},
    }
    good = direct_facts(QUERY, GOOD)
    assert assess(good) == ("compatible", [])
    for facet, patch in changes.items():
        assert assess(direct_facts(QUERY, replace(GOOD, **patch))) == ("excluded", [facet])
    known = ("verified-a", 10, good)
    later = ("verified-b", 1, good)
    unsealed = ("unknown", 100, {**good, "ownership": None})
    incompatible = ("wrong-effects", 99, direct_facts(QUERY, replace(GOOD, **changes["effects"])))
    cases = {
        "higher_score_incompatible": decide(True, (incompatible, known))[0],
        "unknown_alternative": decide(True, (known, unsealed))[0],
        "incomplete_inventory": decide(False, (known,))[0],
        "two_certified": decide(True, (known, later))[0],
        "only_excluded": decide(True, (incompatible,))[0],
        "duplicate_exact_result": decide(True, (known, known))[0],
        "conflicting_evidence_for_same_identity": decide(True, (
            known, (known[0], 20, incompatible[2])
        ))[0],
    }
    assert cases == {"higher_score_incompatible": "bound", "unknown_alternative": "pending",
                     "incomplete_inventory": "pending",
                     "two_certified": "ambiguous", "only_excluded": "no-match",
                     "duplicate_exact_result": "bound", "conflicting_evidence_for_same_identity": "pending"}
    assert decide(True, (incompatible, known)) == ("bound", ["verified-a"])
    assert decide(True, (known, later)) == decide(True, (later, known))
    return {"python": platform.python_version(), "facets": FACETS, "checks": sum(counts.values()),
            "outcomes": counts, "typed_negative_controls": sorted(changes),
            "resolution": cases, "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
