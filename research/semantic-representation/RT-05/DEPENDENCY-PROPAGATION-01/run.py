#!/usr/bin/env python3
"""Compare exact subject and resolved execution identities for a closed graph."""

from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
import platform

HERE = Path(__file__).resolve().parent
POLICIES = ("local_body", "exact_subject", "resolved_execution", "whole_state")


def digest(domain, data):
    framed = json.dumps((domain, data), sort_keys=True, separators=(",", ":")).encode("ascii")
    return sha256(framed).hexdigest()


def resolved_execution(subject, required, bindings):
    exact = tuple((operation, bindings[operation]) for operation in sorted(set(required)))
    return digest("execution/1", (subject, exact))


def model(direct_value, operation, binding3, binding4, sibling, display):
    bindings = {3: binding3, 4: binding4}
    child = digest("literal/1", direct_value)
    contract_reference = ("operation", operation)
    calls = (("direct", 7, child), ("by-contract", 9, contract_reference))
    subject = digest("ordered-body/1", (calls, ("literal", sibling)))
    local_body = (("direct", 7, "helper"), ("by-contract", 9, contract_reference))
    # A separate trace oracle evaluates the declared events without using any address.
    trace = (7, direct_value, 9, operation, bindings[operation], sibling)
    return {
        "profile": [direct_value, operation, binding3, binding4, sibling, display],
        "trace": trace,
        "keys": {
            "local_body": digest("local-body/1", (local_body, sibling)),
            "exact_subject": subject,
            "resolved_execution": resolved_execution(subject, [operation], bindings),
            "whole_state": digest("snapshot/1", (subject, bindings, display)),
        },
    }


def compare(cases):
    counts = {policy: {"safe_reuse": 0, "stale_reuse": 0, "missed_reuse": 0} for policy in POLICIES}
    controls = {}
    for left, right in combinations(cases, 2):
        expected = left["trace"] == right["trace"]
        for policy in POLICIES:
            reused = left["keys"][policy] == right["keys"][policy]
            field = {
                (True, True): "safe_reuse",
                (False, True): "stale_reuse",
                (True, False): "missed_reuse",
            }.get((expected, reused))
            if field:
                counts[policy][field] += 1
            if field == "stale_reuse":
                direct_changed = left["profile"][0] != right["profile"][0]
                axis = "direct body" if direct_changed else "selected binding"
                controls.setdefault(f"{policy}: {axis}", [left["profile"], right["profile"]])
    return counts, controls


def results():
    cases = [
        model(*values) for values in product((1, 2), (3, 4), (10, 11), (10, 11), (30, 31), ("A", "B"))
    ]
    counts, witnesses = compare(cases)
    if counts["resolved_execution"]["stale_reuse"] or counts["resolved_execution"]["missed_reuse"]:
        raise AssertionError("Resolved execution key does not match the finite observation oracle")
    subject = cases[0]["keys"]["exact_subject"]
    singleton = resolved_execution(subject, [3], {3: 10})
    if singleton != resolved_execution(subject, [3, 3], {3: 10, 4: 11}):
        raise AssertionError("An unconsulted binding or duplicate lookup changed the resolved key")
    try:
        resolved_execution(subject, [3], {4: 11})
    except KeyError as error:
        missing = error.args[0]
    else:
        raise AssertionError("Missing consulted binding admitted")
    return {
        "schema": "llmlang-implementation-dependency-propagation/1",
        "python": platform.python_version(),
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "Propagation.lean", "axioms.txt")},
        "coordinates": ["direct value", "operation", "binding 3", "binding 4", "sibling", "display"],
        "case_count": len(cases), "pair_count": len(cases) * (len(cases) - 1) // 2,
        "comparison": counts, "stale_witnesses": witnesses,
        "unresolved_binding_refused": missing, "cases": cases,
    }


if __name__ == "__main__":
    print(json.dumps(results(), indent=2))
