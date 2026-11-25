"""Compare per-edge witnesses and pinned obligation coverage in a finite SPG fragment."""

import argparse
from dataclasses import dataclass, replace
from itertools import product
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_graph import ContentStore, Dependency, digest, make_snapshot


SCOPE = "three-outcome-requirements/1"
LABELS = ("allow", "review", "deny")


@dataclass(frozen=True, order=True)
class Check:
    requirement: str
    design: str
    scope: str
    holds: bool


def outcomes(mask):
    return tuple(label for position, label in enumerate(LABELS) if mask & (1 << position))


def release(store, authority, design, implementation, checks, *, policy):
    """Coverage pins the independently given specification snapshot and exact pairs."""
    requirements = set(authority.mapping.values())
    design_outputs = set(store.get(design).payload)
    supplied = tuple(sorted(checks))
    valid = tuple(Check(address, design, SCOPE, True) for address in sorted(requirements))
    conforms = (
        len(design_outputs) > 0
        and store.get(implementation).dependencies == (Dependency("provides", design),)
        and store.get(implementation).payload in design_outputs
    )
    if policy == "submitted_checks":
        return conforms and all(row.holds for row in supplied)
    if policy != "pinned_recheck":
        raise ValueError(policy)
    if not conforms or supplied != valid:
        return False
    return all(design_outputs <= set(store.get(row.requirement).payload["allowed"]) for row in supplied)


def finite_sweep():
    counts = {"cases": 0, "local_witnesses": 0, "shared_witness": 0, "valid_refinement": 0,
              "false_local_witness_admission": 0, "nonempty_vacuity_failures": 0}
    rows = []
    smallest = None
    for one, two, three, design in product(range(1, 8), range(1, 8), range(1, 8), range(8)):
        requirements = (one, two, three)
        local = all(requirement & design for requirement in requirements)
        intersection = design & one & two & three
        shared = bool(intersection)
        vacuous = all((design & requirement) == design for requirement in requirements)
        universal = bool(design) and vacuous
        design_labels = outcomes(design)
        allowed_lists = [outcomes(requirement) for requirement in requirements]
        separate = [label for label in design_labels if all(label in allowed for allowed in allowed_lists)]
        oracle = bool(design_labels) and len(separate) == len(design_labels)
        if (shared, universal) != (bool(separate), oracle):
            raise AssertionError((requirements, design))
        if universal and not shared:
            raise AssertionError("A nonempty universal refinement must give a joint witness")
        d = {"local_witnesses": local, "shared_witness": shared, "valid_refinement": universal,
             "false_local_witness_admission": local and not shared,
             "nonempty_vacuity_failures": vacuous and not universal}
        counts["cases"] += 1
        for field, accepted in d.items():
            counts[field] += accepted
        rows.append((requirements, design, d))
        if local and not shared and smallest is None:
            smallest = {"requirements": allowed_lists, "design": design_labels}
    if smallest is None or counts["nonempty_vacuity_failures"] != 343:
        raise AssertionError("Expected incompatibility and empty-design controls")
    return {"counts": counts, "smallest_conflict": smallest, "manifest": digest(rows)}


def coverage_controls():
    store = ContentStore()

    def requirement(name, mask):
        return store.put("requirement/1", {"name": name, "allowed": outcomes(mask)})

    allow_either = requirement("payment", 3)
    require_review = requirement("safeguard", 2)
    relaxed = requirement("safeguard", 3)
    force_deny = requirement("safeguard", 4)
    existing = make_snapshot({"payment": allow_either, "safeguard": require_review})
    modified = make_snapshot({"payment": allow_either, "safeguard": relaxed})
    impossible = make_snapshot({"payment": allow_either, "safeguard": force_deny})
    review = store.put("design/1", ["review"])
    ambiguous = store.put("design/1", ["allow", "review"])
    no_output = store.put("design/1", [])
    implementation = store.put("implementation/1", "review", [Dependency("provides", review)])
    proposed = store.put("implementation/1", "review", [Dependency("provides", ambiguous)])
    dead = store.put("implementation/1", "review", [Dependency("provides", no_output)])
    evidence = (Check(allow_either, review, SCOPE, True), Check(require_review, review, SCOPE, True))
    compatible = Check(allow_either, ambiguous, SCOPE, True)
    violation = Check(require_review, ambiguous, SCOPE, False)
    cases = {
        "complete": (existing, review, implementation, evidence, (True, True)),
        "compatible_revision_with_old_receipt": (modified, review, implementation, evidence, (True, False)),
        "compatible_revision_with_rechecked_edge": (modified, review, implementation,
            (evidence[0], Check(relaxed, review, SCOPE, True)), (True, True)),
        "contradictory_requirement_omitted": (impossible, review, implementation, evidence[:1], (True, False)),
        "contradiction_falsely_marked_proven": (impossible, review, implementation,
            (evidence[0], Check(force_deny, review, SCOPE, True)), (True, False)),
        "unsupported_behavior_omitted": (existing, ambiguous, proposed, (compatible,), (True, False)),
        "unsupported_behavior_reported": (existing, ambiguous, proposed, (compatible, violation), (False, False)),
        "wrong_scope": (existing, review, implementation,
            (evidence[0], replace(evidence[1], scope="other/1")), (True, False)),
        "wrong_subject": (existing, review, implementation,
            (evidence[0], replace(evidence[1], design=ambiguous)), (True, False)),
        "empty_design": (existing, no_output, dead,
            (Check(allow_either, no_output, SCOPE, True), Check(require_review, no_output, SCOPE, True)),
            (False, False)),
        "duplicate_check": (existing, review, implementation, (*evidence, evidence[0]), (True, False)),
        "implementation_bound_to_other_design": (existing, review, proposed, evidence, (False, False)),
    }
    output = {}
    for name, (authority, design, impl, receipt, expected) in cases.items():
        actual = tuple(release(store, authority, design, impl, receipt, policy=policy)
                       for policy in ("submitted_checks", "pinned_recheck"))
        if actual != expected:
            raise AssertionError((name, expected, actual))
        output[name] = {"specification_root": authority.root_hash, "checks": [row.__dict__ for row in receipt],
                        "design": design, "impl": impl, "submitted_checks": actual[0],
                        "pinned_recheck": actual[1]}
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    result = {"format": "llmlang-requirement-coverage/1", "python": sys.version.split()[0],
              "sweep": finite_sweep(), "controls": coverage_controls()}
    options.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
