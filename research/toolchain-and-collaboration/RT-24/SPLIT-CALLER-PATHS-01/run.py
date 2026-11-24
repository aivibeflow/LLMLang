"""Check rooted caller-path evidence against the exact candidate Git merge tree."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.candidate_semantic_diff import audit_candidate_semantic_diff
from src.impact_planning import (
    CallSiteDisposition, ImpactedArtifact, OutputOperation, PlannedEdgeKind, PlannedEdgeOperation,
    assign_planned_action_ids, audit_snapshot_incoming, compute_impact_plan_id, plan_impact,
)
from src.semantic_dependency_index import publish_declaration
from src.semantic_graph import ContentStore
from tests import test_candidate_semantic_diff_cip_v2 as cip
from tests import test_rt23_commit_recovery as recovery
from tests import test_rt24_merge_tree_gate as tree
from tests import test_rt24_tree_bound_cip as gate

LEGACY = "legacy-consumer"
MODERN = "modern-consumer"
ROOTS = (LEGACY, MODERN)
PROGRAM = "program/declarations.json"
CASES = ("aligned", "swapped-path-labels", "foreign-path-label", "upper-label-only", "reversed-routing")


def make_program(rewrite):
    store = ContentStore()
    contract = cip.declaration("contract", "contract:provider", {"result": "integer"})
    required = publish_declaration(store, contract)
    provides = {"reference_id": "provided-contract", "relation": "provides_contract",
                "target_hash": required, "target_kind": "contract", "condition": None}

    def function(name, content, sites=()):
        row = cip.declaration("function", name, content, references=(provides,), call_sites=sites)
        return row, publish_declaration(store, row)

    def call(edge, callee):
        return cip.call_site(edge, callee, required)

    leaf, old_leaf = function("leaf:v1", {"value": 1})
    replacement, new_leaf = function("leaf:v2", {"value": 2})
    shared, old_shared = function("shared:v1", {"body": "invoke leaf"}, (call("leaf", old_leaf),))
    fork, new_shared = function("shared:v2", {"body": "invoke leaf"}, (call("leaf", new_leaf),))
    baseline = {"contract": contract, "leaf": leaf, "shared": shared}
    for root in ROOTS:
        baseline[root], _ = function(root, {"body": "invoke shared"}, (call("shared", old_shared),))
    next_consumer, _ = function(rewrite, {"body": "invoke shared"}, (call("shared", new_shared),))
    candidate = {key: value for key, value in baseline.items() if key != "shared"}
    candidate.update({"leaf": replacement, "leaf-v1": leaf, "shared-v1": shared, "shared-v2": fork,
                      rewrite: next_consumer})
    return baseline, candidate


def merged_fixture(repo, rewrite):
    tree.git(repo, "init", "--quiet", "--template=", "--initial-branch=main", "--object-format=sha1")
    before, after = make_program(rewrite)

    def rows(declarations):
        return [tree.row(slot, value) for slot, value in sorted(declarations.items())]

    base = tree.commit(repo, {tree.MANIFEST: tree.manifest(PROGRAM), PROGRAM: rows(before)})
    ours = tree.commit(repo, {"notes.txt": "approved ordinary file\n"})
    tree.git(repo, "switch", "--quiet", "-c", "split", base)
    theirs = tree.commit(repo, {PROGRAM: rows(after)})
    tree.git(repo, "switch", "--quiet", "--detach", ours)
    tree.git(repo, "merge", "--quiet", "--no-ff", "--no-edit", theirs)
    commit = recovery.ref(repo, "HEAD")
    assert tree.git(repo, "show", "-s", "--format=%P", commit).decode().split() == [ours, theirs]
    assert tree.git(repo, "show", f"{commit}:notes.txt") == b"approved ordinary file\n"
    return ours, theirs, commit


def approved_plan(store, before, baseline, candidate, rewrite, path_labels, upper_label):
    old = baseline.mapping
    new = candidate.mapping
    required = old["contract"]

    def output(slot, operation, source=None, path=""):
        return cip.output_record(store, slot, slot, operation, old.get(slot), new.get(slot), source, path)

    preserving, = set(ROOTS) - {rewrite}
    outputs = (
        output("leaf", OutputOperation.REPLACE),
        output("leaf-v1", OutputOperation.ADD),
        output("shared", OutputOperation.REMOVE),
        output("shared-v1", OutputOperation.ADD, old["shared"], path_labels[preserving]),
        output("shared-v2", OutputOperation.ADD, old["shared"], path_labels[rewrite]),
        output(rewrite, OutputOperation.REPLACE, path=upper_label),
    )

    def decision(caller, edge, callee, disposition, replacement, result, path="", output_id=None):
        return cip.decision(caller, edge, "direct", callee, disposition, replacement, result,
                            required, required, required, path, output_id)

    preserve = CallSiteDisposition.PRESERVE
    migrate = CallSiteDisposition.MIGRATE
    decisions = (
        decision(old["shared"], "leaf", old["leaf"], preserve, old["leaf"], old["shared"],
                 path_labels[preserving], "shared-v1"),
        decision(old["shared"], "leaf", old["leaf"], migrate, new["leaf"], new["shared-v2"],
                 path_labels[rewrite], "shared-v2"),
        decision(old[preserving], "shared", old["shared"], preserve, old["shared"], old[preserving]),
        decision(old[rewrite], "shared", old["shared"], migrate, new["shared-v2"], new[rewrite],
                 upper_label, rewrite),
    )

    def edge(output_id, site, old_hash, new_hash):
        return cip.edge_record(output_id, PlannedEdgeKind.CALL_TARGET, f"{site}/direct",
                               PlannedEdgeOperation.REWRITE, "calls", "calls", old_hash, new_hash,
                               old_required=required, new_required=required)

    changes = (
        edge("shared-v2", "leaf", old["leaf"], new["leaf"]),
        edge(rewrite, "shared", old["shared"], new["shared-v2"]),
    )
    impacted = (old["leaf"], old["shared"])
    audits = []
    for value in impacted:
        source = tree.source_evidence(before, store, baseline, value)
        audits.append(audit_snapshot_incoming(tree.checked_source_query(before, store, baseline, source)))
    plan = plan_impact(baseline.root_hash, candidate.root_hash, "split-caller-paths",
                       [ImpactedArtifact(value, "implementation", "approved fixture split") for value in impacted],
                       audits, call_site_decisions=decisions, planned_outputs=outputs, planned_edge_changes=changes)
    actions = assign_planned_action_ids((*plan.actions, cip.action(new["shared-v2"])))
    expanded = replace(plan, actions=actions)
    return replace(expanded, plan_id=compute_impact_plan_id(expanded))


def source_route(inventory, snapshot, root):
    values = {value: slot for slot, value in snapshot.mapping.items()}
    assert len(values) == len(snapshot.mapping)
    path = [root]
    for expected_site in ("shared", "leaf"):
        site, = inventory.declarations[path[-1]]["call_sites"]
        target, = site["targets"]
        assert site["call_site_id"] == expected_site and target["target_id"] == "direct"
        path.append(values[target["target_hash"]])
    assert not inventory.declarations[path[-1]]["call_sites"]
    return path


def path_gate(before, after, baseline, candidate, plan):
    """Check the closed source routes against independently declared entry policy."""
    results = {}
    lower = {d.consumer_path_id: d for d in plan.call_site_decisions if d.call_site_id == "leaf"}
    upper = {d.caller_hash: d for d in plan.call_site_decisions if d.call_site_id == "shared"}
    outputs = {out.output_id: out.logical_key for out in plan.planned_outputs}
    errors = []
    if set(lower) != set(ROOTS):
        errors.append("plan path labels differ from pinned entry slots")
    approved_leaf = {LEGACY: baseline.mapping["leaf"], MODERN: candidate.mapping["leaf"]}
    for root in ROOTS:
        base_route = source_route(before, baseline, root)
        candidate_route = source_route(after, candidate, root)
        assert base_route == [root, "shared", "leaf"]
        entry, caller, leaf = candidate_route
        decision = lower.get(entry)
        if decision is None or (outputs[decision.resulting_output_id], decision.selected_callee_hash) != (
            caller, candidate.mapping[leaf],
        ):
            errors.append(f"{root}: path decision differs from source route")
        entry_decision = upper[baseline.mapping[entry]]
        if entry_decision.selected_callee_hash != candidate.mapping[caller]:
            errors.append(f"{root}: entry decision targets a different shared caller")
        if entry_decision.resulting_output_id and entry_decision.consumer_path_id != entry:
            errors.append(f"{root}: entry decision names a different consumer path")
        if candidate.mapping[leaf] != approved_leaf[root]:
            errors.append(f"{root}: path selects an unapproved provider")
        results[root] = {
            "baseline": base_route, "candidate": candidate_route,
            "observed_candidate_leaf": candidate.mapping[leaf], "approved_leaf": approved_leaf[root],
        }
    return results, errors


def trial(repo, case):
    rewrite = LEGACY if case == "reversed-routing" else MODERN
    labels = {root: root for root in ROOTS}
    if case == "swapped-path-labels":
        labels = {LEGACY: MODERN, MODERN: LEGACY}
    elif case == "foreign-path-label":
        labels[MODERN] = "unregistered-consumer"

    ours, theirs, commit = merged_fixture(repo, rewrite)
    before = tree.read_inventory(repo, ours)
    after = tree.read_inventory(repo, commit)
    store, baseline = tree.import_closed(before)
    _, candidate = tree.import_closed(after)
    tree.publish_rows(after.declarations, store)
    upper_label = LEGACY if case == "upper-label-only" else labels[rewrite]
    plan = approved_plan(store, before, baseline, candidate, rewrite, labels, upper_label)
    audit = audit_candidate_semantic_diff(store, baseline, candidate, plan)
    assert audit.valid, audit.errors
    routes, errors = path_gate(before, after, baseline, candidate, plan)
    assert (not errors) == (case == "aligned"), errors
    prepared = recovery.Prepared("split-caller-paths", after.tree, candidate.root_hash, (ours, theirs), commit)
    approval = gate.Approval(before.tree, before.blob_digest, after.blob_digest, prepared, plan)
    return approval, routes, errors


def replay(scratch):
    results = {}
    for case in CASES:
        checked, existing = scratch / f"{case}-checked", scratch / f"{case}-existing"
        checked.mkdir()
        existing.mkdir()
        approval, routes, errors = trial(checked, case)
        prepared = approval.prepared
        repeat, _, _ = trial(existing, case)
        assert repeat == approval
        existing_result = gate.audit_and_publish(existing, repeat, prepared.candidate)
        assert existing_result == "published"
        if errors:
            assert recovery.ref(checked, recovery.BRANCH) == prepared.parents[0]
            assert recovery.ref(checked, prepared.receipt) is None
            checked_result = "blocked"
        else:
            checked_result = gate.audit_and_publish(checked, approval, prepared.candidate)
            retry = gate.audit_and_publish(checked, approval, prepared.candidate)
            assert checked_result == retry == "published"
            clone = scratch / "clone"
            tree.git(scratch, "clone", "--quiet", "--no-local", str(checked), str(clone))
            tree.git(clone, "fsck", "--full")
            pinned = tree.read_inventory(clone, prepared.candidate)
            _, restored = tree.import_closed(pinned)
            assert restored.root_hash == prepared.semantic_root
            assert {root: source_route(pinned, restored, root) for root in ROOTS} == {
                root: row["candidate"] for root, row in routes.items()
            }
        results[case] = {
            "merge_commit": prepared.candidate, "ordered_parents": prepared.parents,
            "candidate_tree": prepared.tree, "candidate_root": prepared.semantic_root,
            "plan": approval.plan.plan_id, "paths": routes, "path_errors": errors,
            "declared_paths": [
                {"caller": row.caller_hash, "edge": f"{row.call_site_id}/{row.target_id}",
                 "path": row.consumer_path_id, "disposition": row.disposition.value,
                 "resulting_output": row.resulting_output_id, "selected_callee": row.selected_callee_hash}
                for row in approval.plan.call_site_decisions
            ],
            "existing_gate": existing_result, "path_bound_gate": checked_result,
        }
    paired = ("aligned", "swapped-path-labels", "foreign-path-label", "upper-label-only")
    assert len({results[name]["merge_commit"] for name in paired}) == 1
    assert len({results[name]["plan"] for name in paired}) == len(paired)
    return {"format": "rt24-split-caller-paths/1", "python": sys.version.split()[0],
            "git": tree.git(scratch, "--version").decode().strip(), "cases": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-split-caller-paths-") as path:
        data = replay(Path(path))
    args.output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
