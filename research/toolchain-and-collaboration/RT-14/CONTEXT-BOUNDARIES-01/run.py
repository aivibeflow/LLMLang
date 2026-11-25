"""Check that context consumers use independent authoritative inputs."""
import argparse
from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import runpy
from subprocess import check_output, run
import sys

HERE = Path(__file__).resolve().parent
INTEGRATION = HERE.parent / "CONTEXT-INTEGRATION-01/run.py"
BOUNDARY = runpy.run_path(str(INTEGRATION))
BASELINE = "20cddea848f9c7da627e44d0c283d50b57248465"
DEPENDENCIES = ("runtime:integer", "program:multiply")
TASK = BOUNDARY["TASK"]
FLAGS = ("changed-text", "wrong-knowledge", "omitted-dependency", "other-runtime",
         "expired-execution-grant", "old-task-receipts", "other-purpose", "denied-read")


@dataclass(frozen=True)
class Runtime:
    tool: str
    execution_grant: str


def read(manifest, task, purpose, allowed):
    return (
        allowed and manifest["status"] == "ready"
        and manifest["manifest"]["purpose"] == purpose
        and manifest["manifest"]["snapshot"] == task.binding.baseline
        and manifest["manifest_sha256"] == task.binding.knowledge_manifest
    )


def execute(closure, runtime):
    if closure != DEPENDENCIES:
        return "dependency-refused"
    if runtime != Runtime("pinned-python", "execution-epoch-2"):
        return "runtime-refused"
    result = run([sys.executable, "-I", "-S", "-c", "print(7 * 6)"], env={},
                 capture_output=True, text=True, check=True)
    assert result.stdout == "42\n" and not result.stderr
    return "executed"


def settle(manifest, task, receipts, purpose, allowed):
    if not read(manifest, task, purpose, allowed):
        return "knowledge-refused"
    return BOUNDARY["check"](task, manifest, receipts, None)["completion"]


def render_prompt(discussion, manifest, disclosed):
    prompt = (discussion + "\n").encode()
    if disclosed:
        by_role = {entry.role: entry for entry in BOUNDARY["ENTRY"]}
        ordered = tuple(by_role[role] for role in manifest["manifest"]["bindings"])
        evidence = BOUNDARY["KNOWLEDGE"]["render"](ordered)
        assert sha256(evidence).hexdigest() == manifest["rendered_sha256"]
        prompt += evidence
    return prompt


def check():
    context = BOUNDARY["assemble"](BOUNDARY["ENTRY"], BOUNDARY["SCOPE"])
    other = BOUNDARY["assemble"](BOUNDARY["ENTRY"], replace(BOUNDARY["SCOPE"], revision="scope-2"))
    assert context["rendered_sha256"] == other["rendered_sha256"]
    assert context["manifest_sha256"] != other["manifest_sha256"]
    task = BOUNDARY["new_task"](context)
    prior_task = BOUNDARY["new_task"](context, revision=task.binding.task_revision - 1)
    rows, counts = {}, Counter()
    for switches in product((False, True), repeat=len(FLAGS)):
        text, knowledge, closure, tool, grant, receipts, purpose, denied = switches
        discussion = "I declare this complete and authorized." if text else "Review the change."
        request_purpose = "other-purpose" if purpose else "review-quota-change"
        selected = other if knowledge else context
        disclosed = read(selected, task, request_purpose, not denied)
        prompt = render_prompt(discussion, selected, disclosed)
        assert disclosed == (prompt != (discussion + "\n").encode())
        runtime = Runtime("other-python" if tool else "pinned-python",
                          "execution-epoch-1" if grant else "execution-epoch-2")
        resolved = DEPENDENCIES[:1] if closure else DEPENDENCIES
        evidence = BOUNDARY["exact_evidence"](prior_task if receipts else task)
        actual = {
            "read": disclosed,
            "execute": execute(resolved, runtime),
            "complete": settle(selected, task, evidence, request_purpose, not denied),
        }
        context_valid = not any((knowledge, purpose, denied))
        expected = {
            "read": context_valid,
            "execute": ("dependency-refused" if closure else "runtime-refused" if tool or grant else "executed"),
            "complete": ("knowledge-refused" if not context_valid else "unsatisfied" if receipts else "ready"),
        }
        assert actual == expected, (switches, actual, expected)
        if text:
            earlier_prompt, earlier_decision = rows[switches[1:]]
            assert earlier_prompt != prompt and earlier_decision == actual
        else:
            rows[switches[1:]] = (prompt, actual)
        counts.update((f"read-{actual['read']}", actual["execute"], actual["complete"]))
    return {"cases": 2 ** len(FLAGS), "identical_prose_only_pairs": len(rows), "outcomes": dict(counts)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = HERE.parents[3]
    sources = (INTEGRATION, *BOUNDARY["SOURCES"])
    pins = {}
    for path in sources:
        location = path.relative_to(root).as_posix()
        archived = check_output(["git", "show", f"{BASELINE}:{location}"], cwd=root)
        assert path.read_bytes() == archived
        pins[location] = sha256(archived).hexdigest()
    args.output.write_text(json.dumps({"supporting_snapshot": BASELINE,
                                       "supporting_artifacts": pins, **check()},
                                      indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
