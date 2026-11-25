"""Check occurrence and reachability boundaries and reconcile four exact RT-05 ledgers."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess


BASE = "a10c1376ea697afe907f31365b0f4cbaf994f284"
RT05 = "research/semantic-representation/RT-05"


def archived(name):
    path = f"{RT05}/{name}/evidence.json"
    content = subprocess.check_output(["git", "show", f"{BASE}:{path}"])
    return json.loads(content), sha256(content).hexdigest()


def reconcile():
    selection, selection_hash = archived("SPG-SELECTION-BOUNDARY-01")
    ownership, ownership_hash = archived("PARTIAL-RECORD-01")
    aliases, aliases_hash = archived("MUTABLE-REFERENCE-TOPOLOGY-01")
    methods, methods_hash = archived("STATEFUL-BOUND-METHOD-01")
    cases = selection["cases"]
    assert Counter(case["typed_admission"] for case in cases.values()) == {
        "admitted": 7, "refused": 6, "not-run": 1,
    }
    for key in ("binding-target-not-selected", "pin-target-not-selected"):
        case = cases[key]
        assert case["address_membership"]["primary"] == {
            "stored": True, "reachable": True, "selected": False,
        }
        assert case["persistence"] == "admitted" and case["typed_admission"] == "refused"
    for key in ("selection_root", "observations"):
        assert cases["prune-unreachable-storage"][key] == cases["remove-unused-selection"][key]

    owner = ownership["metrics"]
    assert owner["separate_orders"]["abort_mismatch"] == owner["separate_orders"]["completed_mismatch"] == 0
    assert owner["schema_abort"]["abort_mismatch"] == 144
    assert owner["init_for_both"]["completed_mismatch"] == 168
    assert aliases["metrics"]["shared_graph"]["trace_drift"] == 0
    assert aliases["metrics"]["root_local"]["trace_drift"] == 4758
    assert methods["metrics"]["exact"]["changed_recipe_vectors"] == 0
    assert methods["metrics"]["values_only"]["changed_recipe_vectors"] == 135
    return {
        "ledgers": {
            "SPG-SELECTION-BOUNDARY-01": selection_hash, "PARTIAL-RECORD-01": ownership_hash,
            "MUTABLE-REFERENCE-TOPOLOGY-01": aliases_hash, "STATEFUL-BOUND-METHOD-01": methods_hash,
        },
        "archived_graphs": len(cases), "native_ownership_vectors": ownership["native_observations"],
        "graph_alias_classes": aliases["isomorphism_classes"], "bound_method_contexts": methods["contexts"],
    }


def admits(expected_occurrences, occurrences, dependency_targets, archive, selection, binding):
    if occurrences != expected_occurrences:
        return False
    if dependency_targets != {target for _, target in occurrences} or not dependency_targets <= archive:
        return False
    for role, target in occurrences:
        if role == "pinned" and target not in selection:
            return False
        if role == "operation" and (target not in binding or binding[target] not in selection):
            return False
    return True


def occurrence_cases():
    counts = Counter()
    original = (("pinned", "body-a"), ("operation", "operation-a"), ("pinned", "body-a"))
    full_targets = {"body-a", "operation-a"}
    for occurrence_kind, target_kind, archive_ok, selected, binding_state in product(
        ("exact", "reordered", "deduplicated"), ("exact", "missing", "extra"),
        (False, True), (False, True), ("exact", "absent", "retired"),
    ):
        occurrences = {
            "exact": original, "reordered": (original[1], original[0], original[2]),
            "deduplicated": original[:2],
        }[occurrence_kind]
        targets = {"exact": full_targets, "missing": {"body-a"}, "extra": full_targets | {"unused"}}[target_kind]
        archive = full_targets | {"body-b", "retired-body", "unused"} if archive_ok else {"operation-a", "body-b"}
        selection = {"body-a", "body-b"} if selected else {"body-b"}
        binding = {"exact": {"operation-a": "body-b"}, "absent": {},
                   "retired": {"operation-a": "retired-body"}}[binding_state]
        actual = admits(original, occurrences, targets, archive, selection, binding)
        expected = (occurrence_kind, target_kind, archive_ok, selected, binding_state) == (
            "exact", "exact", True, True, "exact",
        )
        assert actual == expected
        counts["admitted" if actual else "refused"] += 1
    return dict(counts)


if __name__ == "__main__":
    print(json.dumps({
        "revision": BASE, "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "prior_evidence": reconcile(), "candidate_scope_matrix": occurrence_cases(),
    }, sort_keys=True, indent=2))
