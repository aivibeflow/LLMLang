#!/usr/bin/env python3
"""Check typed impact plans against full candidate identity reconstruction."""

from collections import Counter
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
import sys
from tarfile import open as open_tar
import tempfile

HERE = Path(__file__).resolve().parent
ARCHIVE = "c1da4dc2753bc3db390f80e0643db911ce870e2c"
PROTOTYPE = "research/PROTOTYPES/DEPENDENCY-GRAPH-01/src"
AXES = ("requirement", "contract", "design", "implementation", "target")
DERIVED = {
    "adequacy": ("formal_clause", ("requirement", "contract")),
    "design_obligation": ("requirement_derived_model", ("design", "contract")),
    "tests": ("test_suite", ("contract", "design")),
    "build": ("build_artifact", ("implementation", "target")),
    "model_proof": ("proof", ("implementation", "contract")),
    "native_validation": ("verification_record", ("build", "tests")),
}
LEAF_KINDS = {"requirement": "requirement", "contract": "caller_contract",
              "design": "requirement_derived_model", "implementation": "implementation"}
EXPECTS = {
    "requirement": {"HUMAN_REVIEW"},
    "caller_contract": {"RE_DERIVE"},
    "formal_clause": {"RE_DERIVE"},
    "requirement_derived_model": {"RE_DERIVE"},
    "implementation": {"REBUILD", "RUN_TESTS"},
    "test_suite": {"REGENERATE_TESTS", "RUN_TESTS"},
    "build_artifact": {"REBUILD", "RUN_TESTS"},
    "proof": {"REPROVE"},
    "verification_record": {"REPROVE"},
}


def instance(semantic, profile):
    store = semantic.ContentStore()
    selected = {name: store.put("typed-axis", {"name": name, "version": state})
                for name, state in zip(AXES, profile, strict=True)}
    for name, (kind, dep_names) in DERIVED.items():
        selected[name] = store.put(kind, {"name": name}, [
            semantic.Dependency("consumes", selected[dep], dep) for dep in dep_names
        ])
    return store, semantic.make_snapshot(selected)


def candidate_impact(store, snapshot, changes):
    addresses = {snapshot.mapping[name] for name in changes}
    for root in tuple(addresses):
        addresses.update(store.dependents(root, transitive=True))
    return {name for name, address in snapshot.mapping.items() if address in addresses}


def verify_plan(semantic, planner, store, before, after, affected):
    kinds = LEAF_KINDS | {name: kind for name, (kind, _) in DERIVED.items()}
    items, audits = [], []
    for name in sorted(affected & kinds.keys()):
        address = before.mapping[name]
        items.append(planner.ImpactedArtifact(address, kinds[name], "changed exact typed inputs"))
        incoming = [(dependent, edge.relation, edge.role, edge.target_hash)
                    for dependent in sorted(store.dependents(address))
                    for edge in store.get(dependent).dependencies if edge.target_hash == address]
        edge_digest = semantic.digest(incoming)
        audits.append(planner.CompletenessAudit(
            planner.CompletenessStatus.SUPPORTED_WITHIN_SCOPE, (), address,
            "typed-change-impact-fixture/1", "closed fixture",
            "exact independently enumerated graph", snapshot_root=before.root_hash,
            target_hash=address, evidence_id=semantic.digest([before.root_hash, address, edge_digest]),
            edge_set_digest=edge_digest, index_schema_version=3, extractor_id="fixture-typed-edges/1",
        ))
    policy = "typed-change-impact-fixture/1"
    plan = planner.plan_impact(before.root_hash, after.root_hash, policy, items, audits)
    actions = {(action.artifact_hash, action.kind.value) for action in plan.actions}
    oracle = {(before.mapping[name], kind)
              for name in affected & kinds.keys() for kind in EXPECTS[kinds[name]]}
    if actions != oracle:
        raise AssertionError((affected, actions, oracle))

    if not audits:
        return plan, ()
    shifted = replace(audits[0], snapshot_root=after.root_hash)
    stale = planner.plan_impact(before.root_hash, after.root_hash, policy, items,
                                [shifted, *audits[1:]])
    missing = planner.plan_impact(before.root_hash, after.root_hash, policy, items, audits[1:])
    for alternative in (stale, missing):
        actual = {action.kind.value for action in alternative.actions
                  if action.artifact_hash == after.root_hash}
        if actual != {"HUMAN_REVIEW", "FULL_REVALIDATION"} or alternative.plan_id == plan.plan_id:
            raise AssertionError(actual)
    return plan, ("stale_snapshot", "missing_audit")


def compare(semantic, planner):
    profiles = list(product((0, 1), repeat=len(AXES)))
    fixture = {bits: instance(semantic, bits) for bits in profiles}
    counts = Counter()
    witnesses = {}
    transcript = sha256()
    for source, target in product(profiles, repeat=2):
        if source == target:
            continue
        store, baseline = fixture[source]
        _, candidate = fixture[target]
        edited = {name for name, old, new in zip(AXES, source, target, strict=True) if old != new}
        impacted = candidate_impact(store, baseline, edited)
        expected = {name for name, base_hash in baseline.selections
                    if base_hash != candidate.mapping[name]}
        if impacted != expected:
            raise AssertionError((edited, impacted, expected))
        plan, checks = verify_plan(semantic, planner, store, baseline, candidate, impacted)
        counts["edit_pairs"] += 1
        counts["checked_actions"] += len(plan.actions)
        for negative in checks:
            counts[negative + "_requires_revalidation"] += 1
        if len(edited) == 1:
            name, = edited
            witnesses.setdefault(name, {
                "impacted": sorted(impacted),
                "audit_bindings": len(plan.audit_bindings),
                "actions": {artifact: sorted({action.kind.value for action in plan.actions
                                              if action.artifact_hash == baseline.mapping[artifact]})
                            for artifact in sorted(impacted)},
            })
        transcript.update(json.dumps([source, target, sorted(impacted), plan.plan_id]).encode() + b"\n")
    assert set(witnesses) == set(AXES)
    return counts, witnesses, transcript.hexdigest()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as location:
        source = subprocess.check_output(["git", "archive", ARCHIVE, PROTOTYPE])
        with open_tar(fileobj=BytesIO(source), mode="r:") as tar:
            tar.extractall(location, filter="data")
        root = Path(location) / PROTOTYPE
        sys.path.insert(0, str(root.parent))
        from src import impact_planning as planner, semantic_graph as semantic
        counts, cases, transcript = compare(semantic, planner)
        hashes = {name: sha256((root / name).read_bytes()).hexdigest()
                  for name in ("impact_planning.py", "semantic_graph.py")}
    print(json.dumps({
        "schema": "llmlang-typed-change-impact/1", "python": platform.python_version(),
        "archive_revision": ARCHIVE, "archive_sha256": hashes,
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "counts": counts, "single_axis_cases": cases, "ordered_plans_sha256": transcript,
    }, indent=2))
