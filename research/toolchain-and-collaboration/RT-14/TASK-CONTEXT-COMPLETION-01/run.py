"""Compare bounded Task Context completion and distinct Git publication permission."""

from collections import Counter
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path


AUTHORITY = {"mutation": "graph-validator", "test": "test-runner",
             "proof": "proof-checker", "review": "review-authority"}
KINDS = frozenset(AUTHORITY)


@dataclass(frozen=True)
class Binding:
    task_id: str = "task-17"
    task_revision: int = 4
    baseline: str = "snap-1"
    candidate: str = "snap-2"
    knowledge_manifest: str = "context-8"
    evidence_policy_revision: int = 3


@dataclass(frozen=True)
class Observation:
    binding: Binding
    obligation: str
    issuer: str
    status: str


@dataclass(frozen=True)
class TaskState:
    binding: Binding = Binding()
    active: bool = True
    live_baseline: str = "snap-1"
    allowed: frozenset[str] = frozenset({"operation-A"})
    changed: frozenset[str] = frozenset({"operation-A"})


@dataclass(frozen=True)
class Grant:
    subject: str = "operator-5"
    action: str = "publish"
    candidate: str = "snap-2"
    epoch: int = 9


@dataclass(frozen=True)
class CompletionReceipt:
    binding: Binding
    changed: frozenset[str]
    sha256: str


def fingerprint(obj):
    serialized = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    return sha256(serialized).hexdigest()


def exact_completion(task, receipts):
    if not task.active:
        return "inactive", None
    if task.live_baseline != task.binding.baseline:
        return "baseline-moved", None
    if task.changed != task.allowed:
        return "wrong-mutation-scope", None

    complete = set()
    for kind, issuer in AUTHORITY.items():
        matches = {item for item in receipts
                   if item.obligation == kind and item.issuer == issuer
                   and item.binding == task.binding}
        if {item.status for item in matches} == {"pass"}:
            complete.update(matches)
    if {item.obligation for item in complete} != KINDS:
        return "unsatisfied", None
    ordered = sorted(complete, key=lambda item: item.obligation)
    digest = fingerprint({
        "binding": asdict(task.binding),
        "changed": sorted(task.changed),
        "evidence": [asdict(item) for item in ordered],
    })
    return "ready", CompletionReceipt(task.binding, task.changed, digest)


def label_completion(receipts):
    return {row.obligation for row in receipts if row.status == "pass"} >= KINDS


def task_id_completion(task, receipts):
    return label_completion(row for row in receipts if row.binding.task_id == task.binding.task_id)


def publication(task, completion, grant, issuer_epoch):
    ready, receipt = completion
    return (ready == "ready" and receipt is not None and grant is not None
            and task.active and task.live_baseline == task.binding.baseline
            and receipt.binding == task.binding and receipt.changed == task.changed == task.allowed
            and grant.subject == "operator-5" and grant.action == "publish"
            and grant.epoch == issuer_epoch and grant.candidate == task.binding.candidate)


def check():
    task = TaskState()
    verify = {kind: Observation(task.binding, kind, issuer, "pass")
              for kind, issuer in AUTHORITY.items()}
    proof = verify["proof"]
    test = verify["test"]
    proof_cases = {
        "valid": (proof,),
        "missing": (),
        "unknown": (replace(proof, status="unknown"),),
        "failed": (replace(proof, status="fail"),),
        "old-task-revision": (replace(proof, binding=replace(proof.binding, task_revision=3)),),
        "old-candidate": (replace(proof, binding=replace(proof.binding, candidate="snap-0")),),
        "untrusted": (replace(proof, issuer="self-report"),),
        "other-task": (replace(proof, binding=replace(proof.binding, task_id="task-42")),),
    }
    test_cases = {
        "valid": (test,),
        "missing": (),
        "other-context": (replace(test, binding=replace(test.binding, knowledge_manifest="context-7")),),
        "same-receipt-twice": (test, test),
        "conflicting": (test, replace(test, status="fail")),
    }
    workspace_cases = {
        "exact": task,
        "expanded": replace(task, changed=frozenset({"operation-A", "operation-B"})),
        "baseline-moved": replace(task, live_baseline="snap-3"),
    }
    grant_cases = {
        "current": Grant(),
        "absent": None,
        "revoked-epoch": Grant(epoch=8),
        "wrong-action": Grant(action="prepare"),
        "wrong-candidate": Grant(candidate="snap-0"),
    }
    status_counts = Counter()
    summary = {strategy: {"completion": 0, "false_completion": 0, "publication": 0,
                          "false_publication": 0}
               for strategy in ("label", "task_id", "exact")}
    samples = {}
    for proof_case, test_case, workspace, active, grant_case in product(
        proof_cases, test_cases, workspace_cases, (True, False), grant_cases
    ):
        state = replace(workspace_cases[workspace], active=active)
        receipts = (*proof_cases[proof_case], *test_cases[test_case],
                    verify["mutation"], verify["review"])
        permitted = grant_case == "current"
        must_complete = (proof_case == "valid" and test_case in {"valid", "same-receipt-twice"}
                         and workspace == "exact" and active)
        must_publish = must_complete and permitted
        result = exact_completion(state, receipts)
        got_publish = publication(state, result, grant_cases[grant_case], issuer_epoch=9)
        if (result[0] == "ready", got_publish) != (must_complete, must_publish):
            raise AssertionError((proof_case, test_case, workspace, active, grant_case, result))
        if result != exact_completion(state, tuple(reversed(receipts))):
            raise AssertionError("Completion changed after reordering receipts")
        status_counts[result[0]] += 1
        label = label_completion(receipts)
        task_id = task_id_completion(state, receipts)
        for name, completed, published in (
            ("label", label, label and permitted),
            ("task_id", task_id, task_id and permitted),
            ("exact", result[0] == "ready", got_publish),
        ):
            facts = summary[name]
            facts["completion"] += completed
            facts["false_completion"] += completed and not must_complete
            facts["publication"] += published
            facts["false_publication"] += published and not must_publish
        if (test_case == "valid" and workspace == "exact" and active and grant_case == "current"
                or proof_case == test_case == "valid" and workspace == "exact" and active):
            key = f"proof={proof_case},grant={grant_case}"
            samples[key] = {"label_ready": label, "task_id_ready": task_id,
                            "exact_status": result[0], "completion_receipt": result[1].sha256 if result[1] else None,
                            "exact_publication": got_publish}

    baseline = exact_completion(task, tuple(verify.values()))
    repeated = exact_completion(task, (*verify.values(), verify["test"]))
    assert baseline == repeated and baseline[1] is not None
    policy_changed = replace(task, binding=replace(task.binding, evidence_policy_revision=4))
    assert exact_completion(policy_changed, tuple(verify.values())) == ("unsatisfied", None)

    publication_controls = {
        "live-baseline-moved": replace(task, live_baseline="snap-3"),
        "task-cancelled": replace(task, active=False),
        "task-revised": replace(task, binding=replace(task.binding, task_revision=5)),
        "changed-candidate": replace(task, binding=replace(task.binding, candidate="snap-3")),
    }
    repeated_publication = {}
    for name, changed in publication_controls.items():
        grant = Grant(candidate=changed.binding.candidate)
        permitted = publication(changed, baseline, grant, issuer_epoch=9)
        assert not permitted
        repeated_publication[name] = permitted

    return {
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "cases": sum(status_counts.values()),
        "exact_statuses": dict(sorted(status_counts.items())),
        "summary": summary,
        "sample_outcomes": samples,
        "checks": {"repeatable_receipt": baseline[1].sha256, "changed_evidence_policy": "unsatisfied",
                   "publication_of_old_receipt": repeated_publication},
    }


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
