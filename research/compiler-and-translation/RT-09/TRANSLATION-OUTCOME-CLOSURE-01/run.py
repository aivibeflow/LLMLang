"""Compose translation outcomes over an exact declared region graph."""

from dataclasses import dataclass, replace
import json
import platform


TARGET = "native-profile-v1"
OBSERVATION = "result-and-ordered-effects-v1"
RUNTIME = "helper-bytes-v1"
DECLARED = {"entry": "entry-v1", "codec": "codec-v1", "preview": "preview-v1"}
ARTIFACTS = {region: f"target-{region}-v1" for region in DECLARED}
DEPENDENCIES = {"entry": ("codec",), "codec": (), "preview": ()}
ROOTS = ("entry", "preview")


@dataclass(frozen=True)
class Evidence:
    region_revision: str
    status: str
    artifact_revision: str
    target: str = TARGET
    observation: str = OBSERVATION
    requirement: str | None = None
    emitted: bool = True


def identity(region):
    return DECLARED[region], ARTIFACTS[region], TARGET, OBSERVATION


def edge_identity(source, target):
    return identity(source), identity(target)


def restriction_key(region, restriction):
    return identity(region), restriction


def assess(root, receipts, edges, available_runtime, approvals):
    stack = [root]
    visited = set()
    blockers = []
    requirements = set()
    while stack:
        region = stack.pop()
        if region in visited:
            continue
        visited.add(region)
        evidence = receipts.get(region)
        if evidence is None:
            blockers.append((region, "unverified", "missing-region-evidence"))
        elif (evidence.region_revision, evidence.artifact_revision, evidence.target,
              evidence.observation) != identity(region):
            blockers.append((region, "unverified", "stale-region-evidence"))
        elif evidence.status in ("unsupported", "unverified"):
            blockers.append((region, evidence.status, "region-disposition"))
        elif not evidence.emitted:
            blockers.append((region, "unverified", "missing-region-artifact"))
        elif evidence.status == "runtime-supported":
            if evidence.requirement in available_runtime:
                requirements.add(("runtime", evidence.requirement))
            else:
                blockers.append((region, "unverified", "required-runtime-unresolved"))
        elif evidence.status == "restricted":
            if restriction_key(region, evidence.requirement) in approvals:
                requirements.add(("restriction", evidence.requirement))
            else:
                blockers.append((region, "unverified", "restriction-approval-unresolved"))
        else:
            assert evidence.status == "exact"
        for successor in DEPENDENCIES[region]:
            if edge_identity(region, successor) not in edges:
                blockers.append((f"{region}->{successor}", "unverified", "edge-evidence-unresolved"))
            stack.append(successor)

    if blockers:
        state = "unsupported" if any(reason[1] == "unsupported" for reason in blockers) else "unverified"
    elif requirements:
        state = "conditional"
    else:
        state = "exact"
    return {
        "state": state,
        "blockers": sorted(blockers),
        "requirements": sorted(requirements),
        "scoped_regions": sorted(visited),
    }


def run_case(receipts, edges, available_runtime, approvals):
    decisions = {root: assess(root, receipts, edges, available_runtime, approvals) for root in ROOTS}
    admitted = [root for root, result in decisions.items() if result["state"] in ("exact", "conditional")]
    return {
        "scope": ("complete" if len(admitted) == len(ROOTS) else "partial" if admitted else "no-verified-root"),
        "admitted": admitted,
        "roots": decisions,
        "emission_only_would_report_complete": all(
            region in receipts and receipts[region].emitted for region in DECLARED
        ),
    }


def study():
    base = {region: Evidence(revision, "exact", ARTIFACTS[region]) for region, revision in DECLARED.items()}
    runtime = base | {"codec": replace(base["codec"], status="runtime-supported", requirement=RUNTIME)}
    restricted = base | {"entry": replace(base["entry"], status="restricted", requirement="no-null")}
    combined = restricted | {"codec": runtime["codec"]}
    unsupported = replace(base["codec"], status="unsupported", emitted=False)
    unresolved = replace(base["codec"], status="unverified")
    blocked_preview = replace(base["preview"], status="unsupported", emitted=False)
    edge = {edge_identity("entry", "codec")}
    grant = {restriction_key("entry", "no-null")}
    helper = {RUNTIME}
    cases = {
        "exact": (base, edge, set(), set(), ("exact", "exact")),
        "bound_runtime": (runtime, edge, helper, set(), ("conditional", "exact")),
        "approved_restriction": (restricted, edge, set(), grant, ("conditional", "exact")),
        "runtime_and_restriction": (combined, edge, helper, grant, ("conditional", "exact")),
        "runtime_absent": (runtime, edge, set(), set(), ("unverified", "exact")),
        "runtime_changed": (runtime, edge, {"helper-bytes-v2"}, set(), ("unverified", "exact")),
        "restriction_unapproved": (restricted, edge, set(), set(), ("unverified", "exact")),
        "restriction_for_other_revision": (
            restricted, edge, set(), {(("entry-v0", ARTIFACTS["entry"], TARGET, OBSERVATION), "no-null")}, ("unverified", "exact")),
        "edge_unchecked": (base, set(), set(), set(), ("unverified", "exact")),
        "edge_bound_to_previous_revision": (
            base, {(identity("entry"), ("codec-v0", ARTIFACTS["codec"], TARGET, OBSERVATION))},
            set(), set(), ("unverified", "exact")),
        "stale_region": (base | {"codec": replace(base["codec"], region_revision="codec-v0")},
                         edge, set(), set(), ("unverified", "exact")),
        "explicitly_unsupported_dependency": (base | {"codec": unsupported}, edge, set(), set(),
                                              ("unsupported", "exact")),
        "emitted_unverified_dependency": (base | {"codec": unresolved}, edge, set(), set(),
                                          ("unverified", "exact")),
        "missing_dependency_evidence": ({"entry": base["entry"], "preview": base["preview"]},
                                        edge, set(), set(), ("unverified", "exact")),
        "missing_emitted_artifact": (base | {"codec": replace(base["codec"], emitted=False)},
                                     edge, set(), set(), ("unverified", "exact")),
        "stale_artifact": (base | {"codec": replace(base["codec"], artifact_revision="target-codec-v0")},
                           edge, set(), set(), ("unverified", "exact")),
        "different_observation_model": (base | {"codec": replace(base["codec"], observation="result-only")},
                                        edge, set(), set(), ("unverified", "exact")),
        "no_admitted_root": (base | {"codec": unresolved, "preview": blocked_preview}, edge, set(), set(),
                             ("unverified", "unsupported")),
    }
    results = {}
    for name, (receipts, edges, available_runtime, approvals, expected) in cases.items():
        decision = run_case(receipts, edges, available_runtime, approvals)
        assert tuple(result["state"] for result in decision["roots"].values()) == expected
        results[name] = decision
    assert results["runtime_and_restriction"]["roots"]["entry"]["requirements"] == [
        ("restriction", "no-null"), ("runtime", RUNTIME)]
    counts = {label: sum(result["scope"] == label for result in results.values())
              for label in ("complete", "partial", "no-verified-root")}
    assert counts == {"complete": 4, "partial": 13, "no-verified-root": 1}
    emission_only = sum(result["emission_only_would_report_complete"] and result["scope"] != "complete"
                        for result in results.values())
    assert emission_only == 10
    return {"python": platform.python_version(), "declared_graph": DEPENDENCIES,
            "scope_counts": counts, "emission_only_false_admissions": emission_only, "results": results}


if __name__ == "__main__":
    print(json.dumps(study(), indent=2, sort_keys=True))
