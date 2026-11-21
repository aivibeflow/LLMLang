"""Bind a caller migration plan to the Git tree that can be published."""

from dataclasses import dataclass, replace
import unittest

from src.candidate_semantic_diff import audit_candidate_semantic_diff
from src.impact_planning import (
    ActionKind, CallSiteDisposition, CompletenessStatus, ImpactedArtifact,
    ImpactPlan, OutputOperation, PlannedEdgeKind, PlannedEdgeOperation,
    audit_snapshot_incoming, compute_impact_plan_id, plan_impact,
)
from src.semantic_dependency_index import publish_declaration
from tests import test_candidate_semantic_diff_cip_v2 as cip
from tests import test_rt23_commit_recovery as recovery
from tests import test_rt24_merge_tree_gate as tree


class Unpublishable(ValueError):
    pass


@dataclass(frozen=True)
class Approval:
    baseline_tree: str
    baseline_inventory: str
    candidate_inventory: str
    prepared: recovery.Prepared
    plan: ImpactPlan


def audit_and_publish(repo, approval, candidate):
    """Fixture gate for an already approved, exact tree and source-audited CIP."""
    before = tree.read_inventory(repo, approval.prepared.parents[0])
    after = tree.read_inventory(repo, candidate)
    if (before.tree, before.blob_digest, after.tree, after.blob_digest) != (
        approval.baseline_tree, approval.baseline_inventory,
        approval.prepared.tree, approval.candidate_inventory,
    ):
        raise Unpublishable("different Git tree or source inventory")
    if candidate != approval.prepared.candidate:
        raise Unpublishable("different prepared commit")

    store, baseline = tree.import_closed(before)
    _, proposed = tree.import_closed(after)
    tree.publish_rows(after.declarations, store)

    audits = {}
    for target, status in approval.plan.audit_statuses:
        evidence = tree.source_evidence(before, store, baseline, target)
        checked = tree.checked_source_query(before, store, baseline, evidence)
        if (status != CompletenessStatus.SUPPORTED_WITHIN_SCOPE.value
                or checked.completeness_status is not CompletenessStatus.SUPPORTED_WITHIN_SCOPE):
            raise Unpublishable("unresolved caller-coverage audit")
        audits[target] = audit_snapshot_incoming(checked)
    planned_targets = {
        edge.baseline_target_hash for edge in approval.plan.planned_edge_changes
        if edge.edge_kind is PlannedEdgeKind.CALL_TARGET and edge.baseline_target_hash is not None
    }
    if not planned_targets <= audits.keys():
        raise Unpublishable("missing audit for planned caller migration")
    observed_sites = {
        (call.caller_hash, call.call_site_id, call.target_id, call.target_hash)
        for audit in audits.values() for call in audit.incoming_call_sites
    }
    decided_sites = {
        (decision.caller_hash, decision.call_site_id, decision.target_id, decision.base_callee_hash)
        for decision in approval.plan.call_site_decisions
    }
    if observed_sites != decided_sites:
        raise Unpublishable("plan does not cover every audited call site")
    expected = tuple(sorted(
        (target, audit.snapshot_root, audit.target_hash, audit.scope, audit.index_schema_version,
         audit.extractor_id, audit.evidence_id, audit.edge_set_digest)
        for target, audit in audits.items()
    ))
    if expected != approval.plan.audit_bindings:
        raise Unpublishable("plan does not bind current source audit")
    if any(action.kind is ActionKind.FULL_REVALIDATION for action in approval.plan.actions):
        raise Unpublishable("full revalidation remains required")
    result = audit_candidate_semantic_diff(store, baseline, proposed, approval.plan)
    if not result.valid:
        raise Unpublishable(f"candidate differs from plan: {result.errors}")
    return recovery.publish(repo, approval.prepared)


class TreeBoundCIPExperiment(unittest.TestCase):
    setUp = tree.MergeTreeGateExperiment.setUp

    def approved(self):
        tree.git(self.repo, "branch", "-m", "main")
        current = tree.commit(self.repo, {
            tree.CALLER: [tree.row("caller", self.caller)],
        })
        before = tree.read_inventory(self.repo, current)
        store, baseline = tree.import_closed(before)
        new_hash = publish_declaration(store, self.new)
        migrated = {**self.caller, "call_sites": [cip.call_site(
            "invoke", new_hash, self.contract_hash, "entry-active",
        )]}
        next_caller = publish_declaration(store, migrated)
        branch = recovery.ref(self.repo, "HEAD")
        self.assertEqual(branch, current)
        tree.git(self.repo, "switch", "--quiet", "--detach", current)
        candidate = tree.commit(self.repo, {
            tree.CALLEE: [tree.row("callee", self.new)],
            tree.CALLER: [tree.row("caller", migrated)],
            "notes.txt": "approved regular-file update\n",
        })
        after = tree.read_inventory(self.repo, candidate)
        _, target = tree.import_closed(after)
        evidence = tree.source_evidence(before, store, baseline, self.old_hash)
        checked = tree.checked_source_query(before, store, baseline, evidence)
        old_caller = baseline.mapping["caller"]
        outputs = (
            cip.output_record(store, "callee-new", "callee", OutputOperation.REPLACE,
                              self.old_hash, new_hash),
            cip.output_record(store, "caller-new", "caller", OutputOperation.REPLACE,
                              old_caller, next_caller),
        )
        migration = cip.decision(
            old_caller, "invoke", "direct", self.old_hash, CallSiteDisposition.MIGRATE,
            new_hash, next_caller, self.contract_hash, self.contract_hash, self.contract_hash,
            resulting_output_id="caller-new", selected_output_id="callee-new",
        )
        delta = cip.edge_record(
            "caller-new", PlannedEdgeKind.CALL_TARGET, "invoke/direct", PlannedEdgeOperation.REWRITE,
            "calls", "calls", self.old_hash, new_hash, "entry-active", "entry-active",
            self.contract_hash, self.contract_hash,
        )
        plan = plan_impact(baseline.root_hash, target.root_hash, "tree-cip-fixture",
            [ImpactedArtifact(self.old_hash, "implementation", "change provider")],
            [audit_snapshot_incoming(checked)], call_site_decisions=[migration],
            planned_outputs=outputs, planned_edge_changes=[delta])
        prepared = recovery.Prepared("tree-cip", after.tree, target.root_hash, (current,), candidate)
        return Approval(before.tree, before.blob_digest, after.blob_digest, prepared, plan)

    def test_exact_migration_tree_and_receipt_are_published(self):
        approved = self.approved()
        candidate = approved.prepared.candidate
        self.assertEqual(audit_and_publish(self.repo, approved, candidate), "published")
        self.assertEqual(audit_and_publish(self.repo, approved, candidate), "published")
        self.assertEqual(recovery.ref(self.repo, recovery.BRANCH), candidate)
        self.assertEqual(recovery.ref(self.repo, approved.prepared.receipt), candidate)

    def test_semantically_equal_tree_with_unapproved_regular_file_is_rejected(self):
        approved = self.approved()
        substitute = tree.commit(self.repo, {"notes.txt": "unapproved bytes\n"})
        inventory = tree.read_inventory(self.repo, substitute)
        self.assertEqual(tree.import_closed(inventory)[1].root_hash, approved.prepared.semantic_root)
        candidate = recovery.commit_object(self.repo, inventory.tree, approved.prepared.parents, "substitute")
        with self.assertRaisesRegex(Unpublishable, "different Git tree"):
            audit_and_publish(self.repo, approved, candidate)
        self.assertEqual(recovery.ref(self.repo, recovery.BRANCH), approved.prepared.parents[0])
        self.assertIsNone(recovery.ref(self.repo, approved.prepared.receipt))

    def test_plan_cannot_drop_exact_source_audit(self):
        approved = self.approved()
        changed = replace(approved.plan, audit_bindings=())
        changed = replace(changed, plan_id=compute_impact_plan_id(changed))
        with self.assertRaisesRegex(Unpublishable, "does not bind"):
            audit_and_publish(self.repo, replace(approved, plan=changed), approved.prepared.candidate)
        self.assertIsNone(recovery.ref(self.repo, approved.prepared.receipt))

    def test_plan_cannot_lose_migration_disposition_or_change_exact_edge(self):
        approved = self.approved()
        missing = replace(approved.plan, call_site_decisions=())
        edge, = approved.plan.planned_edge_changes
        different = replace(approved.plan, planned_edge_changes=(
            replace(edge, candidate_condition="other-guard"),
        ))
        for changed, message in (
            (missing, "cover every audited call site"),
            (different, "candidate differs from plan"),
        ):
            with self.subTest(message=message):
                changed = replace(changed, plan_id=compute_impact_plan_id(changed))
                with self.assertRaisesRegex(Unpublishable, message):
                    audit_and_publish(self.repo, replace(approved, plan=changed),
                                      approved.prepared.candidate)
                self.assertIsNone(recovery.ref(self.repo, approved.prepared.receipt))
