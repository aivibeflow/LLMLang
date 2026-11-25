"""Model shared execution and exact source-occurrence evidence separately."""

from copy import deepcopy
import hashlib
from itertools import product
import json
from pathlib import Path
import platform
import re

SOURCE = re.compile(r"(?m)^[ \t]*(left|right)[ \t]*=[ \t]*(twice\([ \t]*x[ \t]*\))[ \t]+when[ \t]+([pq])[ \t]*$")
SOURCE_VARIANTS = (
    "left = twice(x) when p\nright = twice(x) when q\n",
    "left=twice( x )  when p\n  right = twice(x) when q\n",
    "\n  left = twice(x) when p\n\nright=twice( x) when q\n",
)


def sha_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def identity(record):
    data = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    return sha_bytes(data)


def parse(text):
    matches = list(SOURCE.finditer(text))
    assert len(matches) == 2 and [(m[1], m[3]) for m in matches] == [("left", "p"), ("right", "q")]
    assert len([line for line in text.splitlines() if line.strip()]) == len(matches)
    graph = [{"slot": match[1], "guard": match[3], "operation": "twice"} for match in matches]
    occurrences = [{"slot": match[1], "guard": match[3], "span": list(match.span(2))}
                   for match in matches]
    return graph, occurrences


def exact_map(text, target):
    graph, occurrences = parse(text)
    return {
        "source": sha_bytes(text.encode()),
        "graph": identity(graph), "target": identity(target),
        "links": [row | {"target_instruction": target["uses"][row["slot"]]} for row in occurrences],
    }


def verify_map(text, target, received):
    expected = exact_map(text, target)
    if received["source"] != expected["source"]:
        return "stale-source"
    if received["graph"] != expected["graph"] or received["target"] != expected["target"]:
        return "wrong-artifact"
    if received["links"] != expected["links"]:
        return "wrong-occurrence-coverage"
    return "accepted-exact-map"


def evaluate(operation, x, first, second, *, sharing, write_between):
    values = [None, None]
    trace = []

    def compute(value):
        if operation == "checked" and value < 0:
            raise ArithmeticError("negative argument")
        if operation == "emit":
            trace.append(value)
        return value if operation == "read" else 2 * value

    shared = None
    try:
        if sharing == "eager":
            shared = compute(x)
        for index, guard in enumerate((first, second)):
            if index and write_between:
                x += 1
            if not guard:
                continue
            if sharing == "none":
                values[index] = compute(x)
            else:
                if shared is None:
                    shared = compute(x)
                values[index] = shared
    except ArithmeticError:
        return {"status": "error", "slots": values, "trace": trace}
    return {"status": "return", "slots": values, "trace": trace}


def execution():
    inputs = tuple(product(range(-2, 3), (False, True), (False, True)))
    profiles = (
        ("pure_total", "twice", False, 0, 0),
        ("pure_partial", "checked", False, 0, 2),
        ("observable_emit", "emit", False, 5, 10),
        ("read_across_write", "read", True, 5, 10),
    )
    outcomes = {}
    for profile, operation, write, lazy_expected, eager_expected in profiles:
        rows = {}
        for policy, expected in (("lazy", lazy_expected), ("eager", eager_expected)):
            differences = []
            for args in inputs:
                source = evaluate(operation, *args, sharing="none", write_between=write)
                lowered = evaluate(operation, *args, sharing=policy, write_between=write)
                if source != lowered:
                    differences.append({"input": args, "source": source, "lowered": lowered})
            assert len(differences) == expected
            rows[policy] = {"inputs": len(inputs), "mismatches": len(differences),
                            "first_mismatch": next(iter(differences), None)}
        outcomes[profile] = rows
    return outcomes


def mapping():
    target = {"instructions": [{"operation": "twice", "operand": "x", "instruction": 0}],
              "uses": {"left": 0, "right": 0}}
    versions = [exact_map(source, target) for source in SOURCE_VARIANTS]
    assert len({row["source"] for row in versions}) == 3
    assert len({row["graph"] for row in versions}) == len({row["target"] for row in versions}) == 1
    assert verify_map(SOURCE_VARIANTS[0], target, versions[0]) == "accepted-exact-map"
    assert verify_map(SOURCE_VARIANTS[1], target, versions[0]) == "stale-source"

    missing = deepcopy(versions[0])
    missing["links"].pop()
    swapped = deepcopy(versions[0])
    left, right = swapped["links"]
    left["span"], right["span"] = right["span"], left["span"]
    wrong_target = deepcopy(versions[0])
    wrong_target["target"] = "unknown-target"
    different_operation = deepcopy(target)
    different_operation["instructions"][0]["operation"] = "emit"
    differently_lowered_map = exact_map(SOURCE_VARIANTS[0], different_operation)
    cases = {
        "one_source_span_for_shared_instruction": verify_map(SOURCE_VARIANTS[0], target, missing),
        "swapped_spans_for_identical_source_expressions": verify_map(SOURCE_VARIANTS[0], target, swapped),
        "wrong_generated_identity": verify_map(SOURCE_VARIANTS[0], target, wrong_target),
        "stale_source_revision": verify_map(SOURCE_VARIANTS[1], target, versions[0]),
        "fresh_source_revision": verify_map(SOURCE_VARIANTS[1], target, versions[1]),
        "exact_map_without_semantic_preservation": verify_map(
            SOURCE_VARIANTS[0], different_operation, differently_lowered_map
        ),
    }
    assert list(cases.values()) == ["wrong-occurrence-coverage", "wrong-occurrence-coverage",
                                    "wrong-artifact", "stale-source", "accepted-exact-map", "accepted-exact-map"]
    return {"source_texts": SOURCE_VARIANTS, "target": target, "version_maps": versions, "controls": cases}


if __name__ == "__main__":
    print(json.dumps({
        "schema": "llmlang-rt05-shared-instruction-provenance/1",
        "python": platform.python_version(), "runner_sha256": sha_bytes(Path(__file__).read_bytes()),
        "execution": execution(), "mapping": mapping(),
    }, indent=2))
