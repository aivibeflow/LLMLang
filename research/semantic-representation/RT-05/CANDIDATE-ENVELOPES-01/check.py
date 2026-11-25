"""Check exact, domain-separated candidate envelopes for the bounded identity profile."""

from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import subprocess


BASE = "2426691c3b0200edf9b6dfb8bb5083050b3b7b28"
ROOT = "research/semantic-representation/RT-05"


def key(kind, **fields):
    preimage = json.dumps({"domain": f"llmlang-research/{kind}/1", "fields": fields},
                          ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("ascii")
    return f"{kind}/1/sha256/{sha256(preimage).hexdigest()}"


@dataclass(frozen=True)
class Inputs:
    interface: str = "interface-A"
    contract_value: str = "relation-A"
    contract_profile: str = "observations-A"
    operation_context: str = "call-semantics-A"
    body: str = "body-A"
    exact_dependency: str = "direct-call-A"
    provided_contract: str = "provider-promise-A"
    implementation_context: str = "execution-profile-A"
    class_constraints: str = "target-requirements-A"
    class_criteria: str = "refinement-rule-A"
    other_candidate: str = "implementation-B"
    discovery_scope: str = "scope-A"
    assumptions: str = "assumptions-A"
    verifier: str = "verifier-A"
    evidence_payload: str = "proof-A"
    review_policy: str = "admission-A"
    description: str = "display name"


def envelopes(inputs):
    contract = key("contract", value=inputs.contract_value, profile=inputs.contract_profile)
    operation = key("operation", interface=inputs.interface, contract=contract,
                    call_semantics=inputs.operation_context)
    implementation = key("implementation", body=inputs.body,
                         exact_dependencies=[inputs.exact_dependency],
                         provided_contract=inputs.provided_contract,
                         execution_profile=inputs.implementation_context)
    conformance_class = key("class", operation=operation, constraints=inputs.class_constraints,
                            criterion=inputs.class_criteria)
    candidates = key("candidates", scope=inputs.discovery_scope,
                     members=sorted({implementation, inputs.other_candidate}))
    evidence = key("evidence", implementation=implementation, conformance_class=conformance_class,
                   assumptions=inputs.assumptions, checker=inputs.verifier,
                   proof=inputs.evidence_payload, policy=inputs.review_policy)
    return dict(contract=contract, operation=operation, implementation=implementation,
                conformance_class=conformance_class, candidates=candidates, evidence=evidence)


EXPECTED_FIELDS = {
    "interface": {"operation", "conformance_class", "evidence"},
    "contract_value": {"contract", "operation", "conformance_class", "evidence"},
    "contract_profile": {"contract", "operation", "conformance_class", "evidence"},
    "operation_context": {"operation", "conformance_class", "evidence"},
    "body": {"implementation", "candidates", "evidence"},
    "exact_dependency": {"implementation", "candidates", "evidence"},
    "provided_contract": {"implementation", "candidates", "evidence"},
    "implementation_context": {"implementation", "candidates", "evidence"},
    "class_constraints": {"conformance_class", "evidence"},
    "class_criteria": {"conformance_class", "evidence"},
    "other_candidate": {"candidates"},
    "discovery_scope": {"candidates"},
    "assumptions": {"evidence"},
    "verifier": {"evidence"},
    "evidence_payload": {"evidence"},
    "review_policy": {"evidence"},
    "description": set(),
}


def matrix():
    baseline = envelopes(Inputs())
    scenarios = []
    for changes in (*combinations(EXPECTED_FIELDS, 1), *combinations(EXPECTED_FIELDS, 2)):
        candidate = envelopes(replace(Inputs(), **{name: f"changed-{name}" for name in changes}))
        changed = {name for name in candidate if candidate[name] != baseline[name]}
        expected = set().union(*(EXPECTED_FIELDS[name] for name in changes))
        assert changed == expected
        scenarios.append({"fields": changes, "changed_identities": sorted(changed)})
    assert key("operation", field="x") != key("implementation", field="x")
    assert key("operation", one="x", two="y") == key("operation", two="y", one="x")
    return {"count": len(scenarios), "baseline": baseline, "cases": scenarios}


def archives():
    result = {}
    for name in ("OPERATION-IDENTITY-01", "PROVIDED-CONTRACT-IDENTITY-01", "CONFORMANCE-CLASS-IDENTITY-01"):
        raw = subprocess.check_output(["git", "show", f"{BASE}:{ROOT}/{name}/evidence.json"])
        assert isinstance(json.loads(raw), dict)
        result[name] = sha256(raw).hexdigest()
    return result


if __name__ == "__main__":
    print(json.dumps({
        "revision": BASE, "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "prior_ledgers": archives(), "matrix": matrix(),
    }, sort_keys=True, indent=2))
