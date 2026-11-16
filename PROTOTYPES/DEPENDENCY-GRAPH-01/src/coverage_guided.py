"""Scenario 22: deterministic, coverage-guided finite-domain experiment planning.

This is a planner, not a program executor or a proof of dependency completeness.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from hashlib import sha256
from itertools import combinations, product
import json
from typing import Iterable, Mapping

class PlanningError(ValueError):
    pass

@dataclass(frozen=True)
class Factor:
    name: str
    values: tuple[object, ...]
    feedback_targets: tuple[tuple[object, tuple[str, ...]], ...] = ()

    def __post_init__(self):
        if not self.name or not self.values:
            raise PlanningError("factor needs a name and a non-empty finite domain")
        domain = {_canonical(v) for v in self.values}
        if len(domain) != len(self.values):
            raise PlanningError(f"factor {self.name} has duplicate canonical values")
        seen = set()
        for value, targets in self.feedback_targets:
            key = _canonical(value)
            if key not in domain:
                raise PlanningError(f"feedback guidance value outside domain for {self.name}")
            if key in seen or not targets or any(not t for t in targets):
                raise PlanningError(f"invalid or duplicate feedback guidance for {self.name}")
            seen.add(key)

@dataclass(frozen=True)
class Candidate:
    assignment: tuple[tuple[str, object], ...]
    changed_factors: tuple[str, ...]
    targets: frozenset[str]
    digest: str

@dataclass(frozen=True)
class PlannedExperiments:
    artifact_hash: str
    context_digest: str
    observation_model_digest: str
    baseline: tuple[tuple[str, object], ...]
    candidates: tuple[Candidate, ...]
    target_universe: frozenset[str]
    plan_digest: str

@dataclass
class CoverageLedger:
    """Observed coverage is kept separate from planned/possible coverage."""
    covered: set[str] = field(default_factory=set)
    executed_candidate_digests: set[str] = field(default_factory=set)
    observations: dict[str, set[str]] = field(default_factory=dict)

    def record(self, candidate: Candidate, *, semantic_partitions: Iterable[str] = (),
               branches: Iterable[str] = (), taint_paths: Iterable[str] = (),
               trace_events: Iterable[str] = (), outcome_classes: Iterable[str] = ()) -> None:
        self.covered.update(candidate.targets)
        observed = (set(semantic_partitions) | set(branches) | set(taint_paths)
                    | set(trace_events) | set(outcome_classes))
        self.covered.update(observed)
        self.observations.setdefault(candidate.digest, set()).update(observed)
        self.executed_candidate_digests.add(candidate.digest)

    def coverage_ratio(self, universe: Iterable[str]) -> float:
        targets = set(universe)
        if not targets:
            return 1.0
        return len(targets & self.covered) / len(targets)

def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()

def _target_value(name: str, value: object) -> str:
    return f"value:{name}={_canonical(value)}"

def _target_interaction(items: tuple[tuple[str, object], ...]) -> str:
    body = "&".join(f"{name}={_canonical(value)}" for name, value in items)
    return f"interaction:{len(items)}:{body}"

def _value_targets(factor: Factor, value: object) -> set[str]:
    targets = {_target_value(factor.name, value)}
    if all(type(v) is int for v in factor.values):
        if value == min(factor.values):
            targets.add(f"boundary:{factor.name}:minimum={value}")
        if value == max(factor.values):
            targets.add(f"boundary:{factor.name}:maximum={value}")
    for guided_value, feedback in factor.feedback_targets:
        if _canonical(guided_value) == _canonical(value):
            targets.update(feedback)
    return targets

def build_plan(*, artifact_hash: str, context_digest: str,
               observation_model_digest: str, factors: Iterable[Factor],
               baseline: Mapping[str, object],
               max_interaction_order: int = 2) -> PlannedExperiments:
    factors = tuple(sorted(factors, key=lambda f: f.name))
    if not all((artifact_hash, context_digest, observation_model_digest)):
        raise PlanningError("artifact, context, and observation-model identities are required")
    if not factors or len({f.name for f in factors}) != len(factors):
        raise PlanningError("factors must be non-empty and uniquely named")
    names = {f.name for f in factors}
    if set(baseline) != names:
        raise PlanningError("baseline must specify exactly every declared factor")
    by_name = {f.name: f for f in factors}
    for name, value in baseline.items():
        if _canonical(value) not in {_canonical(v) for v in by_name[name].values}:
            raise PlanningError(f"baseline value outside finite domain for {name}")
    if max_interaction_order < 1:
        raise PlanningError("interaction order must be at least one")
    max_interaction_order = min(max_interaction_order, len(factors))
    baseline_tuple = tuple(sorted(baseline.items()))
    target_universe: set[str] = set()
    raw: dict[str, tuple[tuple[tuple[str, object], ...], tuple[str, ...], frozenset[str]]] = {}
    for order in range(1, max_interaction_order + 1):
        for selected in combinations(factors, order):
            for values in product(*(f.values for f in selected)):
                changed = tuple((f.name, v) for f, v in zip(selected, values)
                                if _canonical(v) != _canonical(baseline[f.name]))
                if not changed:
                    continue
                assignment = dict(baseline)
                assignment.update(dict(changed))
                changed_names = tuple(name for name, _ in changed)
                targets: set[str] = set()
                for factor, value in zip(selected, values):
                    if _canonical(value) != _canonical(baseline[factor.name]):
                        targets.update(_value_targets(factor, value))
                selected_values = tuple((f.name, v) for f, v in zip(selected, values))
                if order >= 2:
                    targets.add(_target_interaction(selected_values))
                for pair in combinations(selected_values, 2):
                    targets.add(_target_interaction(tuple(pair)))
                assignment_tuple = tuple(sorted(assignment.items()))
                target_set = frozenset(targets)
                digest = _digest({"artifact": artifact_hash, "context": context_digest,
                                  "observation_model": observation_model_digest,
                                  "assignment": assignment_tuple,
                                  "changed_factors": changed_names})
                if digest in raw:
                    previous_assignment, previous_changed, previous_targets = raw[digest]
                    raw[digest] = (previous_assignment, previous_changed,
                                   previous_targets | target_set)
                else:
                    raw[digest] = (assignment_tuple, changed_names, target_set)
                target_universe.update(target_set)
    candidates = tuple(Candidate(a, c, t, d) for d, (a, c, t) in sorted(raw.items()))
    plan_digest = _digest({"artifact": artifact_hash, "context": context_digest,
                           "observation_model": observation_model_digest,
                           "baseline": baseline_tuple,
                           "candidates": [c.digest for c in candidates],
                           "target_universe": sorted(target_universe),
                           "max_order": max_interaction_order})
    return PlannedExperiments(artifact_hash, context_digest, observation_model_digest,
                              baseline_tuple, candidates, frozenset(target_universe), plan_digest)

def schedule(plan: PlannedExperiments, ledger: CoverageLedger,
             run_budget: int) -> tuple[Candidate, ...]:
    """Greedy deterministic set-cover scheduler, with stable digest tie-breaking."""
    if run_budget < 0:
        raise PlanningError("run budget cannot be negative")
    remaining = [c for c in plan.candidates
                 if c.digest not in ledger.executed_candidate_digests]
    selected: list[Candidate] = []
    covered = set(ledger.covered)
    while remaining and len(selected) < run_budget:
        scored = [(len(c.targets - covered), c.digest, c) for c in remaining]
        gain, _, best = max(scored, key=lambda row: (row[0], tuple(-ord(ch) for ch in row[1])))
        if gain <= 0:
            break
        selected.append(best)
        covered.update(best.targets)
        remaining.remove(best)
    return tuple(selected)

def coverage_report(plan: PlannedExperiments, ledger: CoverageLedger) -> dict[str, object]:
    missing = sorted(plan.target_universe - ledger.covered)
    return {"covered_count": len(plan.target_universe) - len(missing),
            "target_count": len(plan.target_universe),
            "coverage_ratio": ledger.coverage_ratio(plan.target_universe),
            "uncovered_targets": missing,
            "executed_candidate_count": len(ledger.executed_candidate_digests),
            "candidate_count": len(plan.candidates)}
