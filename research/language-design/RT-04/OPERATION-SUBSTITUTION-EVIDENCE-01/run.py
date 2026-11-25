"""Compare exact operation substitution across independent bounded obligations."""

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PROTOTYPE = ROOT / "research/PROTOTYPES/DEPENDENCY-GRAPH-01"
RUNNER_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
sys.path.insert(0, str(PROTOTYPE))
from src.semantic_graph import digest

DOMAIN = tuple(range(8))
REQUIRED = ("coverage", "observation", "progress", "resource")
CONTRACT = {
    "domain": DOMAIN, "result": "2*x", "trace": ["account"],
    "deadline": "x+3 abstract steps", "memory": "x+2 abstract units",
}
OPERATION = digest({"kind": "scoped-operation-v1", "contract": CONTRACT})
BASE_CONTEXT = {
    "scope": "inputs-0-through-7", "model": "deterministic-v1",
    "schedule": "single-worker-v1", "resource_checker": "abstract-cost-v1",
}
CONTEXT_INPUTS = {
    "coverage": ("scope", "model"),
    "observation": ("scope", "model"),
    "progress": ("scope", "model", "schedule"),
    "resource": ("scope", "model", "resource_checker"),
}


@dataclass(frozen=True)
class Observation:
    value: int | None
    trace: tuple[str, ...]
    steps: int | None
    memory: int | None


def run_provider(provider, value):
    if provider == "narrow" and value == 0:
        return None
    if provider == "divergent" and value == 7:
        return Observation(None, (), None, None)
    step_overhead = {"late": 4, "exact_limits": 3}.get(provider, 1)
    memory_overhead = {"memory_over": 3, "exact_limits": 2}.get(provider, 1)
    return Observation(
        2 * value, ("account", "more") if provider == "wrong_trace" else ("account",),
        value + step_overhead, value + memory_overhead,
    )


def check(provider):
    table = {n: run_provider(provider, n) for n in DOMAIN}
    refutations = {axis: [] for axis in REQUIRED}
    for n, row in table.items():
        if row is None:
            refutations["coverage"].append(n)
            continue
        if row.value is not None and (row.value != 2 * n or row.trace != ("account",)):
            refutations["observation"].append(n)
        if row.steps is None or row.steps > n + 3:
            refutations["progress"].append(n)
        if row.memory is not None and row.memory > n + 2:
            refutations["resource"].append(n)
    return table, refutations


@dataclass(frozen=True)
class Receipt:
    axis: str
    operation: str
    implementation: str
    inputs: str
    outcome: str


def implementation_id(provider):
    return digest({"profile": provider, "provider_model_source": RUNNER_SHA256})


def key(provider, axis, context, *, whole=False):
    projection = context if whole else {role: context[role] for role in CONTEXT_INPUTS[axis]}
    return digest({"kind": "candidate-obligation-v1", "axis": axis, "operation": OPERATION,
                   "implementation": implementation_id(provider), "context": projection})


def receipts(provider, refutations, context=BASE_CONTEXT):
    return [Receipt(axis, OPERATION, implementation_id(provider), key(provider, axis, context),
                    "REFUTED" if refutations[axis] else "CHECKED_IN_FIXTURE") for axis in REQUIRED]


def disposition(provider, supplied, context=BASE_CONTEXT):
    results = {}
    for axis in REQUIRED:
        candidates = [r for r in supplied if r.axis == axis]
        if len(candidates) != 1:
            results[axis] = "MISSING" if not candidates else "AMBIGUOUS"
            continue
        item = candidates[0]
        if (item.operation, item.implementation, item.inputs) != (
            OPERATION, implementation_id(provider), key(provider, axis, context)
        ):
            results[axis] = "STALE_OR_WRONG_SCOPE"
        else:
            results[axis] = item.outcome
    return {"axes": results, "eligible": all(value == "CHECKED_IN_FIXTURE" for value in results.values())}


def main():
    names = ("fast", "exact_limits", "late", "memory_over", "divergent", "narrow", "wrong_trace")
    providers = {}
    for name in names:
        table, refutations = check(name)
        evidence = receipts(name, refutations)
        providers[name] = {
            "implementation": implementation_id(name),
            "observations": {n: asdict(row) if row else None for n, row in table.items()},
            "refutations": refutations,
            "receipts": [asdict(r) | {"identity": digest(asdict(r))} for r in evidence],
            "observation_projection_passes": not refutations["observation"],
            "substitution": disposition(name, evidence),
        }
    assert {name for name, row in providers.items() if row["substitution"]["eligible"]} == {"fast", "exact_limits"}
    assert sum(row["observation_projection_passes"] and not row["substitution"]["eligible"]
               for row in providers.values()) == 4

    success = receipts("fast", check("fast")[1])
    cost_revision = BASE_CONTEXT | {"resource_checker": "abstract-cost-v2"}
    scheduling_revision = BASE_CONTEXT | {"schedule": "single-worker-v2"}
    controls = {
        "missing_resource": disposition("fast", success[:-1]),
        "duplicate_observation": disposition("fast", [*success, success[1]]),
        "different_implementation": disposition("exact_limits", success),
        "different_operation": disposition("fast", [replace(r, operation="other-operation") for r in success]),
        "cost_context_changed": disposition("fast", success, cost_revision),
        "schedule_context_changed": disposition("fast", success, scheduling_revision),
    }
    assert controls["missing_resource"]["axes"]["resource"] == "MISSING"
    assert controls["duplicate_observation"]["axes"]["observation"] == "AMBIGUOUS"
    assert set(controls["different_implementation"]["axes"].values()) == {"STALE_OR_WRONG_SCOPE"}
    assert set(controls["different_operation"]["axes"].values()) == {"STALE_OR_WRONG_SCOPE"}
    assert {axis for axis, outcome in controls["cost_context_changed"]["axes"].items()
            if outcome == "STALE_OR_WRONG_SCOPE"} == {"resource"}
    assert {axis for axis, outcome in controls["schedule_context_changed"]["axes"].items()
            if outcome == "STALE_OR_WRONG_SCOPE"} == {"progress"}
    assert all(not row["eligible"] for row in controls.values())
    context_effects = {}
    for name, context in (("resource_checker", cost_revision), ("schedule", scheduling_revision)):
        exact = [axis for axis in REQUIRED if key("fast", axis, BASE_CONTEXT) == key("fast", axis, context)]
        whole = [axis for axis in REQUIRED
                 if key("fast", axis, BASE_CONTEXT, whole=True) == key("fast", axis, context, whole=True)]
        assert len(exact) == 3 and not whole
        context_effects[name] = {"scoped_keys_retained": exact, "whole_context_keys_retained": whole}

    files = (Path(__file__), PROTOTYPE / "src/semantic_graph.py")
    return {
        "schema": "llmlang-rt04-operation-substitution/1", "python": platform.python_version(),
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        "contract": CONTRACT, "operation": OPERATION, "context": BASE_CONTEXT,
        "providers": providers, "evidence_controls": controls, "context_effects": context_effects,
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
