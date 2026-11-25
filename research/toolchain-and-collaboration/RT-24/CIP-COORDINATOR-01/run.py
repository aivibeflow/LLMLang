"""Gate native Git publication on exact closed-tree CIP v2 obligations."""
import argparse
from dataclasses import dataclass, replace
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
GRAPH = HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
COORDINATOR = HERE.parent / "GIT-CORE-COORDINATOR-01" / "run.py"
sys.path.insert(0, str(GRAPH))

from src.candidate_semantic_diff import audit_candidate_semantic_diff
from src.impact_planning import (
    CallSiteDisposition, CompletenessStatus, ImpactPlan, OutputOperation,
    PlannedEdgeKind, PlannedEdgeOperation, assign_planned_action_ids,
    audit_snapshot_incoming, compute_impact_plan_id,
)
from src.semantic_dependency_index import SemanticObjectError, publish_declaration
from src.semantic_graph import ContentStore
from src.semantic_merge_core import merge_closed, pin_merge_input
from tests import test_candidate_semantic_diff_cip_v2 as cip
from tests.test_candidate_graph_audit import declaration
from tests.test_rt24_merge_tree_gate import (
    GraphImportError, InventoryError, checked_source_query, import_closed,
    publish_rows, read_inventory, source_evidence,
)

spec = spec_from_file_location("fixture_git_coordinator", COORDINATOR)
native = module_from_spec(spec)
sys.modules[spec.name] = native
spec.loader.exec_module(native)
GIT, HEAD = native.GIT, native.HEAD

PATH = {
    "legacy": CallSiteDisposition.PRESERVE,
    "modern": CallSiteDisposition.MIGRATE,
    "adaptive": CallSiteDisposition.ADAPT,
    "forked": CallSiteDisposition.FORK,
}


@dataclass(frozen=True)
class Approval:
    baseline_commit: str
    baseline_tree: str
    common_base: str
    source_commit: str
    candidate_tree: str
    plan: ImpactPlan


def attached(plan):
    return replace(plan, plan_id=compute_impact_plan_id(plan))


def inspect(repo, baseline_commit, candidate_tree):
    before = read_inventory(repo, baseline_commit)
    after = read_inventory(repo, candidate_tree)
    store, baseline = import_closed(before)
    _, candidate = import_closed(after)
    assert publish_rows(after.declarations, store) == candidate
    return before, after, store, baseline, candidate


def audits(inventory, store, snapshot, targets):
    return [audit_snapshot_incoming(checked_source_query(
        inventory, store, snapshot, source_evidence(inventory, store, snapshot, target)
    )) for target in sorted(targets)]


def keys(reports):
    return tuple(sorted((
        item.target_hash, item.snapshot_root, item.target_hash, item.scope,
        item.index_schema_version, item.extractor_id, item.evidence_id, item.edge_set_digest,
    ) for item in reports))


def sites(reports):
    return {
        (call.caller_hash, call.call_site_id, call.target_id, call.target_hash)
        for entry in reports for call in entry.incoming_call_sites
    }


def gate(repo, approval, candidate_tree, publisher=None):
    if approval is None:
        return "plan-required", None
    if candidate_tree != approval.candidate_tree:
        return "wrong-approved-tree", None
    if native.native.lookup(repo, HEAD) != approval.baseline_commit:
        return "stale-head", None
    request = native.Request("merge", approval.common_base, approval.baseline_commit,
                             approval.source_commit)
    if native.role_check(repo, request) is None:
        return "wrong-source-ancestry", None
    try:
        before, _, store, baseline, candidate = inspect(repo, approval.baseline_commit, candidate_tree)
        rebuilt_tree = materialize_merge(repo, approval.common_base, approval.baseline_commit,
                                         approval.source_commit)
    except (GraphImportError, InventoryError, SemanticObjectError):
        return "invalid-inventory", None
    if rebuilt_tree != candidate_tree:
        return "wrong-source-candidate", None
    if before.tree != approval.baseline_tree:
        return "wrong-approval-baseline", None
    plan = approval.plan
    if (plan.baseline_root, plan.candidate_root) != (baseline.root_hash, candidate.root_hash):
        return "wrong-plan-snapshot", None
    scope = {baseline.mapping["leaf"], baseline.mapping["shared"]}
    reports = audits(before, store, baseline, scope)
    if (any(report.status is not CompletenessStatus.SUPPORTED_WITHIN_SCOPE for report in reports)
            or plan.audit_bindings != keys(reports)):
        return "wrong-source-coverage", None
    if sites(reports) != {
        (record.caller_hash, record.call_site_id, record.target_id, record.base_callee_hash)
        for record in plan.call_site_decisions
    }:
        return "incomplete-call-site-plan", None
    result = audit_candidate_semantic_diff(store, baseline, candidate, plan)
    if not result.valid:
        return "candidate-diff-refused", result.errors
    selections = candidate.mapping
    if any(not {path, "shared-" + path} <= selections.keys() for path in PATH):
        return "consumer-path-refused", None
    for path in PATH:
        payload = store.get(selections[path]).payload
        target = payload["call_sites"][0]["targets"][0]["target_hash"]
        if target != selections["shared-" + path]:
            return "consumer-path-refused", None

    if publisher is not None:
        return publisher(repo, approval, result)

    child = native.object_commit(repo, candidate_tree, "CIP checked " + plan.plan_id,
                                 (approval.baseline_commit, approval.source_commit))
    outcome = GIT(repo, "update-ref", HEAD, child, approval.baseline_commit, check=False)
    if outcome.returncode:
        return "ref-update-refused", None
    assert GIT(repo, "rev-parse", f"{child}^{{tree}}") == candidate_tree
    assert native.exact_parents(repo, child) == (approval.baseline_commit, approval.source_commit)
    return "published", {"commit": child, "tree": candidate_tree, "plan": plan.plan_id,
                         "semantic_diff": result.diff_digest,
            "parents": [approval.baseline_commit, approval.source_commit]}


def declarations(policy_name):
    store = ContentStore()
    spec = declaration("contract", "domain", {"type": "int"})
    contract = publish_declaration(store, spec)
    provided = [{"reference_id": "provided", "relation": "provides_contract",
                 "target_hash": contract, "target_kind": "contract"}]

    def function(name, body, target=None, condition=None):
        calls = [] if target is None else [cip.call_site("invoke", target, contract, condition)]
        raw = declaration("function", name, {"body": body}, references=provided, call_sites=calls)
        return raw, publish_declaration(store, raw)

    old_leaf, old_leaf_hash = function("leaf", "old")
    new_leaf, new_leaf_hash = function("leaf", "new")
    shared, shared_hash = function("shared", "shared", old_leaf_hash)
    peer = declaration("contract", "independent", {"value": 0})
    originals = {"contract": spec, "leaf": old_leaf, "shared": shared, "independent": peer}
    revisions = {"contract": spec, "leaf": new_leaf, "leaf-legacy": old_leaf, "independent": peer}
    for path, disposition in PATH.items():
        originals[path], _ = function(path, path, shared_hash)
        if disposition is CallSiteDisposition.PRESERVE:
            revisions["shared-" + path], revisions[path] = shared, originals[path]
        else:
            branch, branch_hash = function("shared", path + "/" + policy_name, new_leaf_hash)
            revisions["shared-" + path] = branch
            revisions[path], _ = function(path, path, branch_hash)
    return originals, revisions


def make_plan(repo, baseline_commit, base, source_commit, candidate_tree):
    before, _, store, baseline, candidate = inspect(repo, baseline_commit, candidate_tree)
    b, n = baseline.mapping, candidate.mapping
    old_leaf, new_leaf = b["leaf"], n["leaf"]
    contract = b["contract"]
    source_reports = audits(before, store, baseline, (old_leaf, b["shared"]))
    outputs = [
        cip.output_record(store, "leaf-new", "leaf", OutputOperation.REPLACE, old_leaf, new_leaf),
        cip.output_record(store, "leaf-old", "leaf-legacy", OutputOperation.ADD, None, old_leaf),
        cip.output_record(store, "shared-remove", "shared", OutputOperation.REMOVE, b["shared"], None),
    ]
    actions = [cip.action(old_leaf), cip.action(new_leaf), cip.action(b["shared"]),
               cip.rewrite_action(b["shared"])]
    decisions, deltas = [], []
    for path, disposition in PATH.items():
        shared_slot = "shared-" + path
        branch = n[shared_slot]
        outputs.append(cip.output_record(
            store, shared_slot, shared_slot, OutputOperation.ADD, None, branch, b["shared"], path,
        ))
        if disposition is CallSiteDisposition.PRESERVE:
            decisions.extend((
                cip.decision(b["shared"], "invoke", "direct", old_leaf, disposition,
                             old_leaf, b["shared"], contract, contract, contract, path, shared_slot),
                cip.decision(b[path], "invoke", "direct", b["shared"], disposition,
                             b["shared"], b[path], contract, contract, contract),
            ))
            continue
        consumer_slot = "consumer-" + path
        outputs.append(cip.output_record(
            store, consumer_slot, path, OutputOperation.REPLACE, b[path], n[path],
            consumer_path_id=path,
        ))
        actions.extend((cip.action(branch), cip.action(n[path]), cip.rewrite_action(b[path])))
        actions.append(cip.action(b[path]))
        decisions.extend((
            cip.decision(b["shared"], "invoke", "direct", old_leaf, disposition,
                         None, None, contract, contract, contract, path, shared_slot, "leaf-new"),
            cip.decision(b[path], "invoke", "direct", b["shared"], CallSiteDisposition.MIGRATE,
                         None, None, contract, contract, contract, path, consumer_slot, shared_slot),
        ))
        deltas.extend((
            cip.edge_record(shared_slot, PlannedEdgeKind.CALL_TARGET, "invoke/direct", PlannedEdgeOperation.REWRITE,
                            "calls", "calls", old_leaf, new_leaf, old_required=contract, new_required=contract),
            cip.edge_record(consumer_slot, PlannedEdgeKind.CALL_TARGET, "invoke/direct", PlannedEdgeOperation.REWRITE,
                            "calls", "calls", b["shared"], branch, old_required=contract, new_required=contract),
        ))
    statuses = tuple(sorted((item.target_hash, item.status.value) for item in source_reports))
    plan = attached(ImpactPlan(
        "", baseline.root_hash, candidate.root_hash, "closed-cip-fixture/1",
        assign_planned_action_ids(tuple(actions)), statuses, keys(source_reports),
        tuple(decisions), tuple(outputs), tuple(deltas),
    ))
    return Approval(baseline_commit, before.tree, base, source_commit, candidate_tree, plan)


def materialize_merge(repo, base, current, proposed):
    store = ContentStore()
    inputs = []
    for commit in (base, current, proposed):
        inventory = read_inventory(repo, commit)
        _, snapshot = import_closed(inventory)
        assert publish_rows(inventory.declarations, store) == snapshot
        inputs.append(pin_merge_input(snapshot, {}))
    merged = merge_closed(store, *inputs)
    if merged.candidate is None:
        return None
    rows = {key: store.get(value).payload for key, value in merged.candidate.snapshot.selections}
    return native.tree(repo, rows)


def prepare(repo):
    repo.mkdir()
    GIT(repo, "init", "--quiet", "--template=", "--initial-branch=research/all", "--object-format=sha1")
    base, first = declarations("first-plan")
    _, revised = declarations("revised-plan")
    common = native.object_commit(repo, native.tree(repo, base), "baseline")
    peer_change = dict(base, independent={**base["independent"], "content": {"value": 9}})
    start = native.object_commit(repo, native.tree(repo, peer_change), "independent change", (common,))
    GIT(repo, "update-ref", HEAD, start)
    first_input = native.object_commit(repo, native.tree(repo, first), "first caller plan", (common,))
    revised_input = native.object_commit(repo, native.tree(repo, revised), "revised caller plan", (common,))
    target = materialize_merge(repo, common, start, first_input)
    rebuilt = materialize_merge(repo, common, start, revised_input)
    assert target and rebuilt and target != rebuilt
    return common, start, (first_input, target), (revised_input, rebuilt)


def check(root):
    results = {}
    for scenario in ("missing-plan", "source-coverage", "omitted-site", "omitted-path", "wrong-edge", "old-tree",
                     "old-snapshot", "invalid-inventory", "wrong-source-ancestry", "tree-not-from-inputs",
                     "authorized-original", "authorized-rebuild"):
        repo = root / scenario
        base, start, first, revised = prepare(repo)
        first_input, target = first
        revised_input, rebuilt = revised
        approved = make_plan(repo, start, base, first_input, target)
        chosen = target
        if scenario == "missing-plan":
            approved = None
        elif scenario == "source-coverage":
            approved = replace(approved, plan=attached(replace(approved.plan, audit_bindings=())))
        elif scenario == "omitted-site":
            decisions = approved.plan.call_site_decisions
            counts = {row.caller_hash: sum(other.caller_hash == row.caller_hash for other in decisions)
                      for row in decisions}
            omitted = next(row for row in decisions if counts[row.caller_hash] == 1)
            approved = replace(approved, plan=attached(replace(
                approved.plan, call_site_decisions=tuple(row for row in decisions if row != omitted),
            )))
        elif scenario == "omitted-path":
            approved = replace(approved, plan=attached(replace(
                approved.plan, call_site_decisions=approved.plan.call_site_decisions[1:],
            )))
        elif scenario == "invalid-inventory":
            _, revised = declarations("first-plan")
            chosen = native.tree(repo, revised, incomplete=True)
            approved = replace(approved, candidate_tree=chosen)
        elif scenario == "wrong-edge":
            edge = approved.plan.planned_edge_changes[0]
            approved = replace(approved, plan=attached(replace(approved.plan, planned_edge_changes=(
                replace(edge, candidate_condition="unapproved-condition"), *approved.plan.planned_edge_changes[1:],
            ))))
        elif scenario == "wrong-source-ancestry":
            approved = replace(approved, common_base=start)
        elif scenario in ("old-tree", "old-snapshot", "tree-not-from-inputs", "authorized-rebuild"):
            chosen = rebuilt
            if scenario == "old-snapshot":
                approved = replace(approved, candidate_tree=rebuilt, source_commit=revised_input)
            elif scenario == "tree-not-from-inputs":
                approved = replace(approved, candidate_tree=rebuilt)
            elif scenario == "authorized-rebuild":
                prior = approved
                approved = make_plan(repo, start, base, revised_input, rebuilt)
                assert (approved.plan.plan_id != prior.plan.plan_id
                        and approved.plan.candidate_root != prior.plan.candidate_root)
        status, detail = gate(repo, approved, chosen)
        expected = {
            "missing-plan": "plan-required", "source-coverage": "wrong-source-coverage",
            "omitted-site": "incomplete-call-site-plan", "omitted-path": "candidate-diff-refused",
            "invalid-inventory": "invalid-inventory", "wrong-edge": "candidate-diff-refused",
            "old-tree": "wrong-approved-tree", "old-snapshot": "wrong-plan-snapshot",
            "wrong-source-ancestry": "wrong-source-ancestry",
            "tree-not-from-inputs": "wrong-source-candidate",
            "authorized-original": "published", "authorized-rebuild": "published",
        }[scenario]
        assert status == expected, (scenario, status, detail)
        head = native.native.lookup(repo, HEAD)
        assert head == (detail["commit"] if expected == "published" else start)
        if expected == "published":
            actual = read_inventory(repo, head)
            assert actual.declarations["independent"]["content"] == {"value": 9}
        results[scenario] = {"status": status, **(detail if expected == "published" else {})}
    return {"git": GIT(root, "--version"), "call_site_decisions": 8,
            "consumer_paths": {path: choice.value for path, choice in PATH.items()},
            "cases": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-cip-coordinator-") as directory:
        evidence = check(Path(directory))
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")


if __name__ == "__main__":
    main()
