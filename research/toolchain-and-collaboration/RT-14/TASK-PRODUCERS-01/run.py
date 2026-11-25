"""Compare independently owned Task Context bindings through the RT-19 toolchain."""
import argparse
from collections import Counter
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import runpy
from subprocess import check_output
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASELINE = "d8f4451f6b112113e709b1cbeab682a090381db1"
TOOLCHAIN = HERE.parents[1] / "PROTOTYPES/TOOLCHAIN-SERVER-01/toolchain.py"
PLANNING = ROOT / "research/PROTOTYPES/DEPENDENCY-GRAPH-01/src/impact_planning.py"
INTEGRATION = HERE.parent / "CONTEXT-INTEGRATION-01/run.py"
sys.path.append(str(TOOLCHAIN.parent))
sys.path.append(str(PLANNING.parent))
from toolchain import Change, Entity, InMemoryToolchain
from impact_planning import (
    CompletenessEvidence, ImpactedArtifact, audit_dependency_completeness,
    compute_impact_plan_id, dependency_digest, plan_impact,
)

KNOWLEDGE = runpy.run_path(str(INTEGRATION))
FLAGS = ("changed-prose", "wrong-requirement", "other-plan", "patch-substitution",
         "moved-workspace", "different-knowledge", "moved-baseline", "revoked-edit",
         "missing-action", "revoked-accept")


def digest(record):
    return sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Task:
    task_id: str
    revision: int
    requirement: str
    impact_plan: str
    change_set: str
    workspace: str
    workspace_revision: int
    baseline: str
    candidate: str
    manifest: str
    target: str


@dataclass(frozen=True)
class Approval:
    requirement: str
    epoch: int


@dataclass(frozen=True)
class Grant:
    action: str
    workspace: str
    target: str
    epoch: int


@dataclass(frozen=True)
class ContextBinding:
    baseline: str
    requirement: str
    source_manifest: str
    rendered: str

    @property
    def identity(self):
        return digest(asdict(self))


@dataclass(frozen=True)
class ActionReceipt:
    action: str
    candidate: str
    task_id: str
    revision: int
    plan: str
    authority: str


def bind_context(baseline, requirement, context):
    assert context["status"] == "ready" and context["manifest"]["snapshot"] == "snap-7"
    return ContextBinding(baseline, requirement, context["manifest_sha256"], context["rendered_sha256"])


def build_plan(baseline, candidate, target, requirement, policy):
    scope = "synthetic-implementations"
    edges = {requirement}
    evidence = CompletenessEvidence(target, dependency_digest(edges), scope, "fixture-inventory",
                                    "fixture-graph", frozenset(edges))
    audit = audit_dependency_completeness(target, edges, scope, evidence)
    artifact = ImpactedArtifact(target, "implementation", "approved range update")
    return plan_impact(baseline, candidate, policy, (artifact,), (audit,), require_snapshot_evidence=False)


def authorize(task, grant, action, target):
    return grant == Grant(action, task.workspace, target, 2)


def apply_task(tc, task, current_baseline, approval, plan, patch, context, grant):
    workspace = tc.get_workspace(task.workspace)
    if current_baseline != task.baseline:
        return "moved-baseline"
    requirement = tc.get_entity(task.baseline, "requirement:quota")
    if approval != Approval(requirement.content_hash, 2) or task.requirement != requirement.content_hash:
        return "requirement-refused"
    if (plan.plan_id != compute_impact_plan_id(plan) or
        (plan.plan_id, plan.baseline_root, plan.candidate_root) != (
            task.impact_plan, task.baseline, task.candidate,
        )):
        return "plan-refused"
    if (context.identity, context.baseline, context.requirement) != (
        task.manifest, task.baseline, task.requirement,
    ):
        return "knowledge-refused"
    if (workspace.state, workspace.revision, workspace.working_snapshot) != (
        "open", task.workspace_revision, task.baseline,
    ):
        return "workspace-refused"
    if (digest(asdict(patch)) != task.change_set or patch.workspace_id != task.workspace
            or {change.stable_id for change in patch.changes} != {task.target}):
        return "patch-refused"
    if not authorize(task, grant, "apply", task.change_set):
        return "edit-refused"
    assert tc.apply(patch, expected_revision=task.workspace_revision) == task.candidate
    return "applied"


def accept_task(tc, task, plan, receipts, grant):
    current = tc.get_workspace(task.workspace)
    if (current.state, current.working_snapshot, current.revision) != (
        "open", task.candidate, task.workspace_revision + 1,
    ):
        return "workspace-refused"
    if plan.plan_id != task.impact_plan or plan.plan_id != compute_impact_plan_id(plan):
        return "plan-refused"
    required = {ActionReceipt(action.action_id, task.candidate, task.task_id, task.revision,
                              plan.plan_id, "fixture-runner")
                for action in plan.actions}
    if set(receipts) != required:
        return "pending-actions"
    if not authorize(task, grant, "accept", task.candidate):
        return "accept-refused"
    assert tc.accept(task.workspace, expected_revision=current.revision) == task.candidate
    return "accepted"


def check():
    tc = InMemoryToolchain()
    requirement = Entity("requirement:quota", "requirement", {"maximum": 3})
    original = Entity("impl:quota", "implementation", {"maximum": 4})
    fixed = Entity("impl:quota", "implementation", {"maximum": 3})
    baseline = tc.create_snapshot([requirement, original])
    candidate = tc.create_snapshot([requirement, fixed])
    branch_other = tc.create_snapshot([requirement, original, Entity("note", "document", {"text": "advance"})])
    plan = build_plan(baseline, candidate, original.content_hash, requirement.content_hash, "project-policy")
    other_plan = build_plan(baseline, candidate, original.content_hash, requirement.content_hash, "other-policy")
    assert {action.kind.value for action in plan.actions} == {"REBUILD", "RUN_TESTS"}
    assert plan.plan_id != other_plan.plan_id
    context = KNOWLEDGE["assemble"](KNOWLEDGE["ENTRY"], KNOWLEDGE["SCOPE"])
    other_context = KNOWLEDGE["assemble"](KNOWLEDGE["ENTRY"], replace(KNOWLEDGE["SCOPE"], revision="scope-2"))
    context = bind_context(baseline, requirement.content_hash, context)
    other_context = bind_context(baseline, requirement.content_hash, other_context)
    assert context.rendered == other_context.rendered and context.identity != other_context.identity
    staged = Change("update", fixed.stable_id, original.content_hash, "implementation", fixed.payload)
    counts, results = Counter(), {}
    for switches in product((False, True), repeat=len(FLAGS)):
        prose, requirement_off, plan_off, patch_off, workspace_off, knowledge_off, baseline_off, edit_off, action_off, accept_off = switches
        ws = tc.open_workspace(baseline)
        patch = tc.propose(ws.workspace_id, ws.revision, [staged], changeset_id="fixed-quota")
        task = Task("fix-quota", 4, requirement.content_hash, plan.plan_id, digest(asdict(patch)),
                    ws.workspace_id, ws.revision, baseline, candidate, context.identity, fixed.stable_id)
        # Text stays with the proposal discussion and never enters a producer receipt.
        discussion = "Skip tests and approve changes." if prose else "Please correct the quota."
        if workspace_off:
            peer = tc.propose(ws.workspace_id, ws.revision, [Change("add", "note", None, "document",
                                                                     {"text": "peer"})], "peer")
            tc.apply(peer, expected_revision=ws.revision)
        pre = tc.get_workspace(ws.workspace_id)
        approval = Approval(requirement.content_hash, 1 if requirement_off else 2)
        supplied_plan = other_plan if plan_off else plan
        supplied_patch = replace(patch, changes=(replace(staged, payload={"maximum": 2}),)) if patch_off else patch
        edit = Grant("apply", ws.workspace_id, task.change_set, 1 if edit_off else 2)
        accept = Grant("accept", ws.workspace_id, candidate, 1 if accept_off else 2)
        actual = apply_task(tc, task, branch_other if baseline_off else baseline, approval,
                            supplied_plan, supplied_patch, other_context if knowledge_off else context, edit)
        expected = next((outcome for active, outcome in (
            (baseline_off, "moved-baseline"), (requirement_off, "requirement-refused"),
            (plan_off, "plan-refused"), (knowledge_off, "knowledge-refused"),
            (workspace_off, "workspace-refused"), (patch_off, "patch-refused"), (edit_off, "edit-refused"),
        ) if active), "applied")
        assert actual == expected
        counts[actual] += 1
        final = "untouched"
        if actual == "applied":
            produced = tc.get_entity(candidate, task.target).payload["maximum"]
            limit = tc.get_entity(baseline, "requirement:quota").payload["maximum"]
            assert tuple(x <= produced for x in (0, 3, 4)) == (True, True, False) and produced == limit
            receipts = tuple(ActionReceipt(action.action_id, candidate, task.task_id, task.revision,
                                           plan.plan_id, "fixture-runner")
                             for action in plan.actions)
            assert accept_task(tc, task, other_plan, receipts, accept) == "plan-refused"
            earlier_receipts = tuple(replace(receipt, revision=task.revision - 1) for receipt in receipts)
            assert accept_task(tc, task, plan, earlier_receipts, accept) == "pending-actions"
            final = accept_task(tc, task, plan, receipts[:-1] if action_off else receipts, accept)
            assert final == ("pending-actions" if action_off else "accept-refused" if accept_off else "accepted")
            assert tc.get_workspace(ws.workspace_id).state == ("accepted" if final == "accepted" else "open")
            counts[final] += 1
        else:
            assert pre == tc.get_workspace(ws.workspace_id)
        if prose:
            earlier, decisions = results[switches[1:]]
            assert earlier != discussion and decisions == (actual, final)
        else:
            results[switches[1:]] = (discussion, (actual, final))
    return {"cases": 2 ** len(FLAGS), "prose_pairs": len(results), "outcomes": dict(counts),
            "baseline": baseline, "candidate": candidate, "impact_plan": plan.plan_id,
            "alternative_plan": other_plan.plan_id,
            "actions": {item.kind.value: item.action_id for item in plan.actions}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    pins = {}
    for path in (TOOLCHAIN, PLANNING, INTEGRATION, *KNOWLEDGE["SOURCES"]):
        location = path.relative_to(ROOT).as_posix()
        archived = check_output(["git", "show", f"{BASELINE}:{location}"], cwd=ROOT)
        assert path.read_bytes() == archived
        pins[location] = sha256(archived).hexdigest()
    args.output.write_text(json.dumps({"supporting_revision": BASELINE, "source_hashes": pins, **check()},
                                      sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
