"""Check native closure and exact propagation across typed and action identities."""

from collections import Counter
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
import subprocess


BASE = "5f01f24c9056dff64baa2de7ec26d4151c2f06fb"
RT05 = "research/semantic-representation/RT-05"


def read(path):
    return subprocess.check_output(["git", "show", f"{BASE}:{RT05}/{path}"])


def archive_counts():
    native_source = read("NATIVE-IMPLEMENTATION-IDENTITY-01/evidence.json")
    dependency_source = read("DEPENDENCY-PROPAGATION-01/evidence.json")
    native = json.loads(native_source)
    dependency = json.loads(dependency_source)
    rows = list(native["rows"])
    pairs = list(combinations(rows, 2))
    native_collisions = {
        key: sum(a[key] == b[key] and a["observed"] != b["observed"] for a, b in pairs)
        for key in ("caller_only_key", "implementation_key", "fixture_evidence_key")
    }
    assert native_collisions == native["pairs_with_same_key_and_distinct_observations"]
    marker_changes = [a["caller_build_action"] != b["caller_build_action"]
                      and a["implementation_key"] == b["implementation_key"] for a, b in pairs
                      if (a["abi"], a["delta"]) == (b["abi"], b["delta"])]
    assert len(marker_changes) == native["distinct_marker_recipe_pairs"] and all(marker_changes)
    axioms = read("DEPENDENCY-PROPAGATION-01/axioms.txt")
    assert b"propext" in axioms
    return {
        "source_sha256": [sha256(raw).hexdigest() for raw in (native_source, dependency_source, axioms)],
        "native_pairs": len(pairs), "native_collision_counts": native_collisions,
        "native_recipe_changes_without_resolved_change": len(marker_changes),
        "typed_dependency_pairs": dependency["pair_count"],
        "typed_dependency_key_counts": dependency["comparison"],
    }


def identities(mode, changes):
    def atom(name):
        return name, name in changes

    exact_callee = (atom("provider"), atom("callee-contract"))
    call_target = exact_callee if mode == "direct" else atom("operation")
    caller = atom("typed-body"), call_target, atom("semantic-configuration")
    recipe = caller, atom("target"), atom("abi"), atom("toolchain"), atom("build-configuration")
    native = (caller, atom("native-output"), exact_callee, atom("target"), atom("abi"),
              atom("runtime"), atom("runtime-configuration"))
    evidence = native, atom("checker"), atom("assumptions")
    return {"typed": caller, "recipe": recipe, "native": native, "evidence": evidence}


RECIPE_ONLY = {"toolchain", "build-configuration"}
NATIVE_ONLY = {"native-output", "runtime", "runtime-configuration"}
BOTH_NATIVE_RECIPE = {"target", "abi"}
ALL = {"typed-body", "semantic-configuration"}
EVIDENCE_ONLY = {"checker", "assumptions"}
CONDITIONAL = {"provider", "callee-contract", "operation"}
FIELDS = sorted(RECIPE_ONLY | NATIVE_ONLY | BOTH_NATIVE_RECIPE | ALL | EVIDENCE_ONLY | CONDITIONAL)


def expected_changes(mode, changed):
    typed = (ALL | ({"provider", "callee-contract"} if mode == "direct" else {"operation"})) & changed
    action = bool(typed or changed & (RECIPE_ONLY | BOTH_NATIVE_RECIPE))
    native = bool(typed or changed & (NATIVE_ONLY | BOTH_NATIVE_RECIPE | {"provider", "callee-contract"}))
    verify = native or bool(changed & EVIDENCE_ONLY)
    return {key for key, changed in (("typed", typed), ("recipe", action), ("native", native), ("evidence", verify))
            if changed}


def field_matrix():
    totals = Counter()
    for mode, count in product(("direct", "abstract"), (1, 2)):
        base = identities(mode, set())
        for edit in combinations(FIELDS, count):
            changed = set(edit)
            observed = identities(mode, changed)
            actual = {key for key, value in observed.items() if value != base[key]}
            assert actual == expected_changes(mode, changed)
            totals[mode] += 1
    return {"edit_checks": dict(totals), "fields": FIELDS}


if __name__ == "__main__":
    print(json.dumps({
        "revision": BASE, "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "archive": archive_counts(), "field_matrix": field_matrix(),
    }, sort_keys=True, indent=2))
