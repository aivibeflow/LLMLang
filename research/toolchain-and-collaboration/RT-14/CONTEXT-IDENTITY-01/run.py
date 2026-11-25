"""Exercise independent Knowledge Context, prompt, and build cache identities."""
import argparse
from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path


@dataclass(frozen=True)
class Inputs:
    object_value: str = "f(x)=x+1"
    dependency: str = "runtime@a"
    snapshot: str = "snapshot-a"
    provenance: str = "source-approval-a"
    selection_rule: str = "selection-rule-a"
    purpose: str = "check"
    read_grant: str = "context-read-a"
    reader: str = "reader-a"
    advisory_text: str = "Review arithmetic."
    rendering_prefix: str = "## Context"
    build_tool: str = "compiler-a"
    build_options: str = "debug"
    build_grant: str = "build-a"


def key(domain, *values):
    encoded = json.dumps((domain, values), sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def identities(spec):
    object_id = key("semantic-object/v1", "definition", spec.object_value)
    dependency_id = key("dependency-closure/v1", object_id, spec.dependency)
    optional_id = key("supporting-source/v1", spec.advisory_text)
    context_id = key("knowledge-context/v1", spec.snapshot, spec.purpose, spec.reader,
                     spec.read_grant, spec.selection_rule, spec.provenance,
                     object_id, dependency_id, optional_id)
    prompt = f"{spec.rendering_prefix}\n{spec.object_value}\n{spec.advisory_text}\n".encode()
    prompt_id = sha256(prompt).hexdigest()
    action_id = key("build-action/v1", dependency_id, spec.build_tool,
                    spec.build_options, spec.build_grant)
    return {
        "object": object_id, "dependency": dependency_id, "context": context_id,
        "prompt": prompt_id, "build-action": action_id,
    }


# The expected invalidations are specified independently of the key construction.
TRANSITIONS = (
    ("object_value", "f(x)=x+2", {"object", "dependency", "context", "prompt", "build-action"}),
    ("dependency", "runtime@b", {"dependency", "context", "build-action"}),
    ("snapshot", "snapshot-b", {"context"}),
    ("provenance", "source-approval-b", {"context"}),
    ("selection_rule", "selection-rule-b", {"context"}),
    ("purpose", "explain", {"context"}),
    ("read_grant", "context-read-b", {"context"}),
    ("reader", "reader-b", {"context"}),
    ("advisory_text", "Check integer addition.", {"context", "prompt"}),
    ("rendering_prefix", "## Evidence", {"prompt"}),
    ("build_tool", "compiler-b", {"build-action"}),
    ("build_options", "release", {"build-action"}),
    ("build_grant", "build-b", {"build-action"}),
)


def authorize(observed, previous, read_allowed, built_allowed):
    matches = {kind: value == previous[kind] for kind, value in observed.items()}
    return {
        "context": read_allowed and matches["context"],
        "prompt": read_allowed and matches["prompt"],
        "build-action": built_allowed and matches["build-action"],
    }


def check():
    base = Inputs()
    original = identities(base)
    invalidations, accepted, wrong_substitutions = Counter(), Counter(), Counter()
    singles = {}
    for switches in product((False, True), repeat=len(TRANSITIONS)):
        selected = [transition for active, transition in zip(switches, TRANSITIONS) if active]
        subject = replace(base, **{field: value for field, value, _ in selected})
        modified = identities(subject)
        expected_changed = set().union(*(scopes for _, _, scopes in selected))
        changed = {kind for kind, value in modified.items() if original[kind] != value}
        assert changed == expected_changed, (selected, changed, expected_changed)
        invalidations.update(changed)
        if len(selected) == 1:
            singles[selected[0][0]] = sorted(changed)
        for left, right in combinations(original, 2):
            for assumed, needed in ((left, right), (right, left)):
                if assumed not in changed and needed in changed:
                    wrong_substitutions[f"{assumed}=>{needed}"] += 1

        for read_allowed, build_allowed in product((False, True), repeat=2):
            reuse = authorize(modified, original, read_allowed, build_allowed)
            for target, reused in reuse.items():
                permitted = build_allowed if target == "build-action" else read_allowed
                assert reused == (permitted and target not in expected_changed)
                accepted[target] += reused

    assert authorize(original, original, False, True) == {
        "context": False, "prompt": False, "build-action": True,
    }
    assert authorize(original, original, True, False) == {
        "context": True, "prompt": True, "build-action": False,
    }
    assert wrong_substitutions["prompt=>context"] and wrong_substitutions["context=>prompt"]
    assert wrong_substitutions["dependency=>build-action"] and wrong_substitutions["object=>dependency"]
    return {
        "identity_comparisons": 2 ** len(TRANSITIONS),
        "access_and_reuse_comparisons": 4 * 2 ** len(TRANSITIONS),
        "invalidations": dict(invalidations),
        "permitted_reuse": dict(accepted),
        "false_reuse_by_preceding_key": dict(wrong_substitutions),
        "single_mutations": singles,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(check(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
