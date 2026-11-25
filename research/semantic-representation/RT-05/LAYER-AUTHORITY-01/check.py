"""Reconcile pinned typed SPG results across admission, refinement and correspondence."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess


REVISION = "262b1e140cf2d4cef191ac94f89faf94c64bb86f"
RT05 = "research/semantic-representation/RT-05"
PROTOTYPE = "research/PROTOTYPES/DEPENDENCY-GRAPH-01"
CAPABILITIES = {
    "evaluate-typed": frozenset(("persisted", "typed")),
    "claim-layered-refinement": frozenset(("persisted", "typed", "scope", "refinement")),
    "locate-source": frozenset(("persisted", "typed", "source")),
    "use-generated": frozenset(("persisted", "typed", "generated")),
    "attribute-generated": frozenset(("persisted", "typed", "source", "generated", "map")),
}


def read(path):
    return subprocess.check_output(["git", "show", f"{REVISION}:{path}"])


def fixture(name):
    path = f"{RT05}/{name}/evidence.json"
    raw = read(path)
    return json.loads(raw), {path: sha256(raw).hexdigest()}


def check_fixture_controls():
    layer, sources = fixture("PER-INPUT-REFINEMENT-01")
    scope, scope_digest = fixture("SOURCE-OCCURRENCE-01")
    shared, shared_digest = fixture("SHARED-INSTRUCTION-PROVENANCE-01")

    for path, digest in layer["source_sha256"].items():
        assert sha256(read(f"{RT05}/PER-INPUT-REFINEMENT-01/{path}")).hexdigest() == digest
    assert len(layer["axiom_audit"]) == 5
    assert all(entry.endswith("does not depend on any axioms") for entry in layer["axiom_audit"])
    counts = layer["counts"]
    assert counts["layered_admission"] == 49
    assert counts["pointwise_only"] - counts["layered_admission"] == counts["pointwise_lacks_coverage"] == 176
    assert counts["projected_misses_pointwise_violation"] == 928

    for name, evidence in (("SOURCE-OCCURRENCE-01", scope), ("SHARED-INSTRUCTION-PROVENANCE-01", shared)):
        assert sha256(read(f"{RT05}/{name}/run.py")).hexdigest() == evidence["runner_sha256"]

    layouts = list(scope["layouts"].values())
    assert len({layout["source_sha256"] for layout in layouts}) == 6
    assert len({layout["graph_root"] for layout in layouts}) == 1
    assert len({layout["graph_sha256"] for layout in layouts}) == 1
    for layout in layouts:
        assert sha256(layout["source_utf8"].encode()).hexdigest() == layout["source_sha256"]
    assert scope["cross_revision_coordinate_mismatches"] == 28
    assert scope["swapped_spans"]["revision_and_bounds_accept"]
    assert not scope["swapped_spans"]["occurrence_revalidation_accept"]

    shared_control = shared["mapping"]["controls"]
    assert shared_control["one_source_span_for_shared_instruction"] == "wrong-occurrence-coverage"
    assert shared_control["exact_map_without_semantic_preservation"] == "accepted-exact-map"
    assert shared["execution"]["pure_partial"]["eager"]["mismatches"] == 2

    pinned = {**sources, **scope_digest, **shared_digest}
    for path in ("src/spg_representation.py", "src/spg_admission.py",
                 "tests/test_spg_representation.py", "tests/test_spg_admission.py"):
        full_path = f"{PROTOTYPE}/{path}"
        pinned[full_path] = sha256(read(full_path)).hexdigest()
    return {
        "pinned_sha256": pinned,
        "layer_counts": counts,
        "kernel_axiom_audit": layer["axiom_audit"],
        "source_revisions": len(layouts), "shared_typed_roots": 1,
        "cross_revision_coordinate_mismatches": scope["cross_revision_coordinate_mismatches"],
        "shared_instruction_controls": shared_control,
    }


def ready(evidence):
    return tuple(name for name, required in CAPABILITIES.items() if required <= evidence)


def check_policy():
    dimensions = ("persisted", "typed", "scope", "refinement", "source", "generated", "map")
    counts = Counter()
    for observed in product((False, True), repeat=len(dimensions)):
        persisted, typed, scope, refinement, source, generated, mapping = observed
        expected = {
            "evaluate-typed": persisted and typed,
            "claim-layered-refinement": persisted and typed and scope and refinement,
            "locate-source": persisted and typed and source,
            "use-generated": persisted and typed and generated,
            "attribute-generated": persisted and typed and source and generated and mapping,
        }
        evidence = {key for key, present in zip(dimensions, observed, strict=True) if present}
        result = ready(evidence)
        assert set(result) == {claim for claim, accepted in expected.items() if accepted}
        counts.update(result)
    return {"states": 2 ** len(dimensions), "eligible": dict(counts)}


def run():
    return {
        "revision": REVISION, "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "controls": check_fixture_controls(), "policy_checks": check_policy(),
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
