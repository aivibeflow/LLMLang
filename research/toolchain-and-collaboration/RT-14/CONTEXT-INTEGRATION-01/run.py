"""Compose pinned Knowledge Context with Task Context completion and authority."""

from dataclasses import asdict, replace
import hashlib
from itertools import permutations
import json
from pathlib import Path
import platform
import runpy
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASELINE = "971f11e4f6e05bffbbb814062f16e7ecd1e30990"
SOURCES = (
    HERE.parent / "KNOWLEDGE-CONTEXT-01/run.py",
    HERE.parent / "TASK-CONTEXT-COMPLETION-01/run.py",
)
KNOWLEDGE, TASK = (runpy.run_path(str(source)) for source in SOURCES)
ENTRY = KNOWLEDGE["BASIS"]
SCOPE = KNOWLEDGE["Scope"]()
REQUIRED = {entry.role: entry.reference() for entry in ENTRY[:2]}
BUDGET = 50


def assemble(entries, scope, budget=BUDGET):
    return KNOWLEDGE["exact"](entries, scope, budget, REQUIRED, {"note"})


def new_task(knowledge, revision=4, baseline="snap-7"):
    binding = TASK["Binding"](
        task_revision=revision, baseline=baseline, candidate="snap-8",
        knowledge_manifest=knowledge["manifest_sha256"],
    )
    return TASK["TaskState"](binding=binding, live_baseline=baseline)


def exact_evidence(task):
    return tuple(TASK["Observation"](task.binding, kind, issuer, "pass")
                 for kind, issuer in TASK["AUTHORITY"].items())


def check(task, proposal_context, receipts, grant):
    if proposal_context["status"] != "ready":
        return {"completion": "knowledge-" + proposal_context["status"], "publish": False}
    if proposal_context["manifest"]["snapshot"] != task.binding.baseline:
        return {"completion": "knowledge-baseline-mismatch", "publish": False}
    if proposal_context["manifest_sha256"] != task.binding.knowledge_manifest:
        return {"completion": "knowledge-revision-mismatch", "publish": False}
    completion = TASK["exact_completion"](task, receipts)
    return {
        "completion": completion[0], "receipt": completion[1].sha256 if completion[1] else None,
        "publish": TASK["publication"](task, completion, grant, issuer_epoch=9),
    }


def exercise():
    context = assemble(ENTRY, SCOPE)
    original = new_task(context)
    receipts = exact_evidence(original)
    grant = TASK["Grant"](candidate=original.binding.candidate)
    renewed = assemble(ENTRY, replace(SCOPE, revision="scope-2"))
    same_text_other_source = assemble(
        (*ENTRY[:2], replace(ENTRY[2], source="design#2")), SCOPE,
    )
    omitted_optional = assemble(ENTRY, SCOPE, budget=23)
    assert renewed["rendered_sha256"] == same_text_other_source["rendered_sha256"] == context["rendered_sha256"]
    assert len({item["manifest_sha256"] for item in (context, renewed, same_text_other_source)}) == 3
    renewed_task = new_task(renewed, revision=original.binding.task_revision + 1)
    other_baseline = new_task(context, baseline="snap-6")
    missing = assemble((ENTRY[0], ENTRY[2]), SCOPE)
    denied = assemble(ENTRY, replace(SCOPE, read=SCOPE.read - {"test#1"}))
    corrupt = assemble((ENTRY[0], replace(ENTRY[1], content="different test"), ENTRY[2]), SCOPE)
    assert missing == denied == {"status": "unavailable"}

    cases = {
        "original": (original, context, receipts, grant, "ready", True),
        "same-prompt-new-scope": (original, renewed, receipts, grant, "knowledge-revision-mismatch", False),
        "same-prompt-different-provenance": (
            original, same_text_other_source, receipts, grant, "knowledge-revision-mismatch", False,
        ),
        "changed-optional-selection": (
            original, omitted_optional, receipts, grant, "knowledge-revision-mismatch", False,
        ),
        "missing-required-source": (original, missing, receipts, grant, "knowledge-unavailable", False),
        "required-source-not-readable": (original, denied, receipts, grant, "knowledge-unavailable", False),
        "required-source-digest-mismatch": (
            original, corrupt, receipts, grant, "knowledge-required-bytes-mismatch", False,
        ),
        "refreshed-task-old-receipts": (renewed_task, renewed, receipts, grant, "unsatisfied", False),
        "refreshed-task-exact-receipts": (
            renewed_task, renewed, exact_evidence(renewed_task), grant, "ready", True,
        ),
        "valid-completion-without-publication-authority": (original, context, receipts, None, "ready", False),
        "valid-completion-with-revoked-grant": (
            original, context, receipts, replace(grant, epoch=8), "ready", False,
        ),
        "knowledge-from-other-baseline": (
            other_baseline, context, exact_evidence(other_baseline), grant, "knowledge-baseline-mismatch", False,
        ),
        "active-branch-moved": (
            replace(original, live_baseline="snap-9"), context, receipts, grant, "baseline-moved", False,
        ),
        "unapproved-work": (
            replace(original, changed=frozenset({"operation-A", "operation-B"})), context,
            receipts, grant, "wrong-mutation-scope", False,
        ),
    }
    output = {}
    for name, (task, manifest, evidence, authority, expected, publish) in cases.items():
        actual = check(task, manifest, evidence, authority)
        assert (actual["completion"], actual["publish"]) == (expected, publish), name
        assert check(task, manifest, tuple(reversed(evidence)), authority) == actual
        output[name] = {
            "task_binding": asdict(task.binding), "live_baseline": task.live_baseline,
            "affected_operations": sorted(task.changed), "knowledge": manifest,
            "evidence": [asdict(item) for item in evidence],
            "grant": asdict(authority) if authority else None, "outcome": actual,
        }

    invariances = 0
    for source_order in permutations(ENTRY):
        for evidence_order in permutations(receipts):
            assert check(original, assemble(source_order, SCOPE), evidence_order, grant) == output["original"]["outcome"]
            invariances += 1
    assert invariances == 144
    return {"independent_required_refs": REQUIRED, "cases": output,
            "source_and_evidence_permutations": invariances}


def main():
    pins = {}
    for source in SOURCES:
        relative = str(source.relative_to(ROOT))
        archived = subprocess.check_output(["git", "show", f"{BASELINE}:{relative}"], cwd=ROOT)
        assert archived == source.read_bytes()
        pins[relative] = hashlib.sha256(archived).hexdigest()
    print(json.dumps({
        "baseline": BASELINE, "python": platform.python_version(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_sha256": pins, **exercise(),
    }, indent=2))


if __name__ == "__main__":
    main()
