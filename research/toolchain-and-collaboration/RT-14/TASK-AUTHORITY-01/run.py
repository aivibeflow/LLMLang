"""Exercise Task Context completion and existing RT-16 authorization separately."""
import argparse
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from itertools import product
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parents[2]
POLICY = RESEARCH / "security" / "PROTOTYPES" / "RT-16-AUTHORIZATION-01" / "policy.py"
COMPLETION = HERE.parent / "TASK-CONTEXT-COMPLETION-01" / "run.py"
GIT = HERE.parents[1] / "RT-20" / "EXACT-TREE-ACCEPTANCE-01" / "run.py"
REPOSITORY = "fixture/research-all"
NOW = 100


def load(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


policy = load("fixture_rt16_policy", POLICY)
context = load("fixture_rt14_context", COMPLETION)
native = load("fixture_rt20_git", GIT)
AGENT = policy.Principal("author", policy.PrincipalKind.AGENT)
REVIEWER = policy.Principal("reviewer", policy.PrincipalKind.HUMAN)


def check_scope(repo, task, evidence, request):
    status, receipt = context.exact_completion(task, evidence)
    if status != "ready":
        return "completion-" + status
    if request.repository != REPOSITORY or request.base_revision != receipt.binding.baseline:
        return "task-action-scope"
    if request.action == policy.Action.COMMIT:
        if request.target != receipt.binding.candidate or native.lookup(repo, native.HEAD) != receipt.binding.baseline:
            return "task-action-scope"
    elif request.action == policy.Action.PUSH:
        if request.target != native.lookup(repo, native.HEAD):
            return "task-action-scope"
        tree, parent = native.git(repo, "show", "-s", "--format=%T%n%P", request.target).splitlines()
        if (tree, parent) != (receipt.binding.candidate, receipt.binding.baseline):
            return "task-action-scope"
    else:
        return "unsupported-action"
    return "matched"


def evaluate(repo, task, evidence, request, cap, approval, ledger):
    scope = check_scope(repo, task, evidence, request)
    if scope != "matched":
        return scope, None
    decision = policy.authorize(request, cap, approval, NOW, ledger.used)
    return decision.reason, decision


def inputs(request):
    capability = policy.Capability(request.actor.subject, REPOSITORY, frozenset({request.action}),
                                   request.base_revision)
    cap_cases = {
        "exact": capability, "missing": None,
        "wrong-actor": replace(capability, subject="different"),
        "wrong-repo": replace(capability, repository="fixture/other"),
        "wrong-base": replace(capability, snapshot="older"),
        "wrong-action": replace(capability, actions=frozenset({policy.Action.VALIDATE})),
    }
    approval = policy.Approval(REVIEWER, request.binding, "nonce-" + request.action.value, NOW + 10)
    acceptance = {
        "exact": approval, "missing": None,
        "expired": replace(approval, expires_at=NOW),
        "wrong-target": replace(approval, binding=replace(request, target="other").binding),
        "wrong-approver": replace(approval, approver=AGENT),
    }
    return cap_cases, acceptance


def matrix(repo, task, evidence, request, ledger):
    caps, approvals = inputs(request)
    results = []
    cap_expected = {"missing": "missing-capability", "wrong-actor": "wrong-principal",
                    "wrong-repo": "wrong-repository", "wrong-base": "stale-snapshot",
                    "wrong-action": "action-not-granted"}
    approval_expected = {"missing": "approval-required", "expired": "approval-expired",
                         "wrong-target": "approval-binding-mismatch", "wrong-approver": "approver-is-not-human",
                         "exact": "authorized"}
    for complete, cap, approval in product((False, True), caps, approvals):
        actual, _ = evaluate(repo, task, evidence if complete else evidence[:-1], request,
                             caps[cap], approvals[approval], ledger)
        expected = (cap_expected.get(cap, approval_expected[approval])
                    if complete else "completion-unsatisfied")
        assert actual == expected
        results.append({"action": request.action.value, "complete": complete, "capability": cap,
                        "approval": approval, "result": actual})
    return results


def fixture_task(base, tree):
    task = context.TaskState(
        binding=context.Binding(baseline=base, candidate=tree), live_baseline=base,
    )
    evidence = tuple(context.Observation(task.binding, kind, issuer, "pass")
                     for kind, issuer in context.AUTHORITY.items())
    return task, evidence


def run(root):
    repo, remote = root / "workspace", root / "bare"
    repo.mkdir()
    remote.mkdir()
    baseline = native.setup(repo, "sha1", "files")
    tree = native.tree(repo, 3, 3)
    task, evidence = fixture_task(baseline, tree)
    ledger = policy.ApprovalLedger()
    commit_request = policy.Request(AGENT, policy.Action.COMMIT, REPOSITORY, baseline, tree)
    results = matrix(repo, task, evidence, commit_request, ledger)
    assert native.lookup(repo, native.HEAD) == baseline
    cap, approval = inputs(commit_request)
    _, commit_decision = evaluate(repo, task, evidence, commit_request, cap["exact"], approval["exact"], ledger)
    assert ledger.reserve(commit_decision)
    commit = native.git(repo, "commit-tree", tree, "-p", baseline, payload="authorized fixture\n")
    native.git(repo, "update-ref", native.HEAD, commit, baseline)
    assert ledger.complete(commit_decision.nonce)

    push_request = policy.Request(AGENT, policy.Action.PUSH, REPOSITORY, baseline, commit)
    results += matrix(repo, task, evidence, push_request, ledger)
    native.git(remote, "init", "--bare", "--quiet", "--template=", "--initial-branch=research/all")
    assert native.lookup(remote, native.HEAD) is None
    cap_push, approval_push = inputs(push_request)
    mismatch, _ = evaluate(repo, task, evidence, push_request, cap_push["exact"], approval["exact"], ledger)
    assert mismatch == "approval-binding-mismatch"
    _, push_decision = evaluate(repo, task, evidence, push_request, cap_push["exact"], approval_push["exact"], ledger)
    assert ledger.reserve(push_decision)
    native.git(repo, "push", "--quiet", str(remote), f"{push_request.target}:{native.HEAD}")
    assert ledger.complete(push_decision.nonce)
    assert native.lookup(remote, native.HEAD) == commit
    replay, _ = evaluate(repo, task, evidence, push_request, cap_push["exact"], approval_push["exact"], ledger)
    assert replay == "approval-replayed"
    new_context = replace(task, binding=replace(task.binding, task_revision=task.binding.task_revision + 1))
    stale, _ = evaluate(repo, new_context, evidence, push_request, cap_push["exact"], approval_push["exact"], ledger)
    assert stale == "completion-unsatisfied"

    exact_destination, moving_destination = root / "exact-destination", root / "moving-destination"
    for destination in (exact_destination, moving_destination):
        destination.mkdir()
        native.git(destination, "init", "--bare", "--quiet", "--template=",
                   "--initial-branch=research/all")
    later_approval = replace(approval_push["exact"], nonce="nonce-same-object-new-request")
    _, granted = evaluate(repo, task, evidence, push_request, cap_push["exact"], later_approval, ledger)
    assert ledger.reserve(granted)
    advanced = native.git(repo, "commit-tree", native.tree(repo, 4, 4), "-p", commit,
                          payload="new fixture head\n")
    native.git(repo, "update-ref", native.HEAD, advanced, commit)
    native.git(repo, "push", "--quiet", str(exact_destination), f"{push_request.target}:{native.HEAD}")
    assert ledger.complete(granted.nonce)
    # In a separate disposable destination, demonstrate the branch-resolution control.
    native.git(repo, "push", "--quiet", str(moving_destination), f"{native.HEAD}:{native.HEAD}")
    assert native.lookup(exact_destination, native.HEAD) == commit
    assert native.lookup(moving_destination, native.HEAD) == advanced

    race = root / "race"
    race.mkdir()
    parent = native.setup(race, "sha1", "files")
    race_tree = native.tree(race, 5, 5)
    contender = native.tree(race, 8, 8)
    race_task, race_evidence = fixture_task(parent, race_tree)
    race_request = policy.Request(AGENT, policy.Action.COMMIT, REPOSITORY, parent, race_tree)
    race_ledger = policy.ApprovalLedger()
    rcaps, rapprovals = inputs(race_request)
    _, intent = evaluate(race, race_task, race_evidence, race_request, rcaps["exact"], rapprovals["exact"],
                         race_ledger)
    assert race_ledger.reserve(intent)
    selected = native.git(race, "commit-tree", race_tree, "-p", parent, payload="pending fixture\n")
    other = native.git(race, "commit-tree", contender, "-p", parent, payload="external fixture\n")
    native.git(race, "update-ref", native.HEAD, other, parent)
    rejected = native.git(race, "update-ref", native.HEAD, selected, parent, check=False)
    assert rejected.returncode != 0 and native.lookup(race, native.HEAD) == other
    assert race_ledger.release(intent.nonce)

    allowed = sum(row["result"] == "authorized" for row in results)
    assert allowed == 2 and len(results) == 120
    return {
        "git": native.git(root, "--version"),
        "admission_checks": len(results), "authorized_in_matrix": allowed,
        "native_commit": {"tree": tree, "parent": baseline, "commit": commit}, "native_local_push": commit,
        "commit_approval_cannot_authorize_push": mismatch, "push_approval_replay": replay,
        "push_after_local_head_moves": {"exact_refspec": commit, "branch_refspec_control": advanced},
        "task_revision_change": stale, "concurrent_git_head_change": "ref-CAS-refused; reservation released",
        "matrix": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-task-authority-") as scratch:
        result = run(Path(scratch))
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
