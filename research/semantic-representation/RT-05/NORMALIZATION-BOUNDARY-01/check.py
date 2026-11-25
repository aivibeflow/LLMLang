"""Check canonical record roles and occurrence order in a finite SPG profile."""

from collections import Counter
from hashlib import sha256
from itertools import combinations, permutations, product
import json
from pathlib import Path
import subprocess


BASE = "70bd54d3b44c2ee5b018bd8d194b06110176e551"
RT05 = "research/semantic-representation/RT-05"
FIELDS = ("left", "middle", "right")
OPERANDS = ("literal", "emit", "fallible")
CONTRACT = ((), ("close",), ("close", "close"))


def canonical(rows, contract):
    fields = tuple(sorted(rows))
    order = tuple(name for name, op in rows if op != "literal")
    return fields, order, tuple(sorted(set(contract)))


def interpret_source(rows, failures):
    trace = []
    output = []
    for field, op in rows:
        value = FIELDS.index(field) + 1
        if op != "literal":
            trace.append(field)
        if op == "fallible" and field in failures:
            return "error", field, tuple(trace)
        output.append((field, value))
    return "return", tuple(sorted(output)), tuple(trace)


def interpret_graph(graph, failures):
    fields, sequence, _ = graph
    modes = dict(fields)
    failed_at = next((index for index, field in enumerate(sequence)
                      if modes[field] == "fallible" and field in failures), None)
    if failed_at is not None:
        return "error", sequence[failed_at], sequence[:failed_at + 1]
    return "return", tuple((field, FIELDS.index(field) + 1) for field, _ in fields), sequence


def check():
    masks = tuple({field for field, present in zip(FIELDS, selection, strict=True) if present}
                  for selection in product((False, True), repeat=len(FIELDS)))
    cases = []
    normalization_checks = 0
    for roles, ordering in product(product(OPERANDS, repeat=3), permutations(FIELDS)):
        modes = dict(zip(FIELDS, roles, strict=True))
        source = tuple((field, modes[field]) for field in ordering)
        graph = canonical(source, CONTRACT)
        for contract in permutations(CONTRACT):
            assert canonical(source, (*contract, contract[0])) == graph
            normalization_checks += 1
        fields, ordered, contract = graph
        restored = tuple((field, modes[field]) for field in ordered)
        restored += tuple((field, op) for field, op in fields if op == "literal")
        assert canonical(restored, contract) == graph
        oracle = tuple(interpret_source(source, failed) for failed in masks)
        assert tuple(interpret_graph(graph, failed) for failed in masks) == oracle
        cases.append((graph, oracle))
    counts = Counter()
    for (first, first_outcome), (second, second_outcome) in combinations(cases, 2):
        if first == second:
            counts["canonical_same_pairs"] += 1
            assert first_outcome == second_outcome
        if first[0] == second[0] and first_outcome != second_outcome:
            counts["field_only_false_equal_pairs"] += 1
    return {
        "source_cases": len(cases), "graph_classes": len({graph for graph, _ in cases}),
        "value_and_trace_observations": len(cases) * len(masks),
        "outer_set_checks": normalization_checks, "idempotence_checks": len(cases), **counts,
    }


def previous_ledgers():
    result = {}
    for study in ("CHECKED-REASSOCIATION-01", "NAMED-RECORD-01", "OWNED-SPG-01"):
        path = f"{RT05}/{study}/evidence.json"
        raw = subprocess.check_output(["git", "show", f"{BASE}:{path}"])
        ledger = json.loads(raw)
        assert ledger["python"] == "3.12.14"
        result[study] = (sha256(raw).hexdigest(), ledger)
    _, reassociate = result["CHECKED-REASSOCIATION-01"]
    assert reassociate["counts"]["checked_complete_mismatches"] == 672 + 688
    _, owned = result["OWNED-SPG-01"]
    assert owned["profile_pairs"] == 900 and owned["observations_per_path"] == 8192
    return result


if __name__ == "__main__":
    result = check()
    previous = previous_ledgers()
    _, record = previous["NAMED-RECORD-01"]
    assert result["graph_classes"] == record["policies"]["ordered_effects"]["classes"]
    assert result["field_only_false_equal_pairs"] == record["policies"]["field_map"]["distinct_behavior_pairs"]
    print(json.dumps({
        "base": BASE, "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "pinned_previous_ledgers": {key: digest for key, (digest, _) in previous.items()}, "results": result,
    }, sort_keys=True, indent=2))
