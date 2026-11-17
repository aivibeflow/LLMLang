"""Scenario 24: adaptive, evidence-triggered interaction discovery.

Planning only: this module does not execute programs or infer causal truth.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from itertools import combinations, product
import json
from typing import Iterable, Mapping

from .coverage_guided import Factor


class AdaptiveError(ValueError):
    pass


class EvidenceStatus(str, Enum):
    OBSERVED_BEHAVIORAL_INFLUENCE = "OBSERVED_BEHAVIORAL_INFLUENCE"
    INTERNAL_PATH_CHANGE_ONLY = "INTERNAL_PATH_CHANGE_ONLY"
    NO_OBSERVED_DIFFERENCE = "NO_OBSERVED_DIFFERENCE"
    OBSERVED_INTERACTION = "OBSERVED_INTERACTION"
    NO_INTERACTION_OBSERVED = "NO_INTERACTION_OBSERVED"
    INCONCLUSIVE = "INCONCLUSIVE"


class ExperimentKind(str, Enum):
    SINGLE_INTERVENTION = "SINGLE_INTERVENTION"
    FACTORIAL_BLOCK = "FACTORIAL_BLOCK"


def _canonical(value: object) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise AdaptiveError(f"value is not canonical JSON: {exc}") from exc


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AdaptiveCandidate:
    artifact_hash: str
    context_digest: str
    observation_model_digest: str
    baseline: tuple[tuple[str, object], ...]
    replicates_per_cell: int
    kind: ExperimentKind
    factor_scope: tuple[str, ...]
    factor_levels: tuple[tuple[object, object], ...]
    cells: tuple[tuple[tuple[str, object], ...], ...]
    targets: frozenset[str]
    root_digest: str
    digest: str
    retry_index: int = 0
    trigger_digests: tuple[str, ...] = ()

    @property
    def cell_cost(self) -> int:
        return len(self.cells) * self.replicates_per_cell


@dataclass(frozen=True)
class AdaptivePlan:
    artifact_hash: str
    context_digest: str
    observation_model_digest: str
    factors: tuple[Factor, ...]
    baseline: tuple[tuple[str, object], ...]
    singles: tuple[AdaptiveCandidate, ...]
    pairwise: tuple[AdaptiveCandidate, ...]
    related_pairs: frozenset[tuple[str, str]]
    max_interaction_order: int
    max_retries: int
    replicates_per_cell: int
    exploration_fraction: float
    plan_digest: str


@dataclass(frozen=True)
class FeedbackRecord:
    candidate: AdaptiveCandidate
    status: EvidenceStatus
    guidance_tags: tuple[str, ...] = ()
    observed_targets: tuple[str, ...] = ()


@dataclass
class AdaptiveLedger:
    """Execution and observed feedback are deliberately separate dimensions."""
    records: dict[str, FeedbackRecord] = field(default_factory=dict)
    executed_targets: set[str] = field(default_factory=set)
    observed_targets: set[str] = field(default_factory=set)

    def record(self, candidate: AdaptiveCandidate, status: EvidenceStatus,
               *, guidance_tags: Iterable[str] = (),
               observed_targets: Iterable[str] = ()) -> None:
        raw_status = getattr(status, "value", status)
        try:
            status = EvidenceStatus(raw_status)
        except (TypeError, ValueError) as exc:
            raise AdaptiveError(f"unsupported evidence status: {raw_status}") from exc
        if candidate.digest in self.records:
            raise AdaptiveError("candidate result already recorded")
        tags = tuple(sorted(set(guidance_tags)))
        observed = tuple(sorted(set(observed_targets)))
        if any(not isinstance(x, str) or not x for x in tags + observed):
            raise AdaptiveError("feedback tags and targets must be non-empty strings")
        self.records[candidate.digest] = FeedbackRecord(candidate, status, tags, observed)
        self.executed_targets.update(candidate.targets)
        self.observed_targets.update(observed)


def _make_candidate(*, artifact_hash: str, context_digest: str,
                    observation_model_digest: str,
                    baseline: Mapping[str, object],
                    factor_scope: tuple[str, ...],
                    factor_levels: tuple[tuple[object, object], ...],
                    factor_domains: Mapping[str, tuple[object, ...]],
                    replicates_per_cell: int,
                    retry_index: int = 0,
                    trigger_digests: Iterable[str] = ()) -> AdaptiveCandidate:
    if len(factor_scope) != len(factor_levels) or not factor_scope:
        raise AdaptiveError("factor scope and two-level designs must align")
    if replicates_per_cell < 1:
        raise AdaptiveError("replicates_per_cell must be at least one")
    if tuple(sorted(factor_scope)) != factor_scope or len(set(factor_scope)) != len(factor_scope):
        raise AdaptiveError("factor scope must be sorted and unique")
    for name, levels in zip(factor_scope, factor_levels):
        if len(levels) != 2 or _canonical(levels[0]) == _canonical(levels[1]):
            raise AdaptiveError("each factor must have exactly two distinct selected levels")
        if any(_canonical(v) not in {_canonical(x) for x in factor_domains[name]}
               for v in levels):
            raise AdaptiveError(f"selected level outside domain for {name}")
    cells = []
    for bits in product((0, 1), repeat=len(factor_scope)):
        assignment = dict(baseline)
        for bit, name, levels in zip(bits, factor_scope, factor_levels):
            assignment[name] = levels[bit]
        cells.append(tuple(sorted(assignment.items())))
    kind = (ExperimentKind.SINGLE_INTERVENTION if len(factor_scope) == 1
            else ExperimentKind.FACTORIAL_BLOCK)
    targets = {f"factor:{name}" for name in factor_scope}
    targets.update(f"value:{name}={_canonical(value)}"
                   for name, levels in zip(factor_scope, factor_levels)
                   for value in levels)
    if len(factor_scope) > 1:
        body = "&".join(f"{n}={_canonical(pair[0])}|{_canonical(pair[1])}"
                        for n, pair in zip(factor_scope, factor_levels))
        targets.add(f"interaction:{len(factor_scope)}:{body}")
    identity = {
        "artifact": artifact_hash, "context": context_digest,
        "observation_model": observation_model_digest,
        "kind": kind.value, "scope": factor_scope,
        "factor_levels": factor_levels, "cells": tuple(cells),
        "replicates_per_cell": replicates_per_cell,
    }
    root = _digest(identity)
    digest = _digest({"root": root, "retry": retry_index})
    return AdaptiveCandidate(
        artifact_hash, context_digest, observation_model_digest,
        tuple(sorted(baseline.items())), replicates_per_cell, kind,
        factor_scope, factor_levels, tuple(cells), frozenset(targets),
        root, digest, retry_index,
        tuple(sorted(set(trigger_digests))),
    )


def build_adaptive_plan(*, artifact_hash: str, context_digest: str,
                        observation_model_digest: str,
                        factors: Iterable[Factor],
                        baseline: Mapping[str, object],
                        related_pairs: Iterable[tuple[str, str]] = (),
                        max_interaction_order: int = 3,
                        max_retries: int = 1,
                        replicates_per_cell: int = 2,
                        exploration_fraction: float = 0.2) -> AdaptivePlan:
    factors = tuple(sorted(factors, key=lambda f: f.name))
    if not all((artifact_hash, context_digest, observation_model_digest)):
        raise AdaptiveError("artifact, context, and observation-model identities are required")
    if not factors or len({f.name for f in factors}) != len(factors):
        raise AdaptiveError("factors must be non-empty and uniquely named")
    if set(baseline) != {f.name for f in factors}:
        raise AdaptiveError("baseline must specify exactly the declared factors")
    for factor in factors:
        if _canonical(baseline[factor.name]) not in {_canonical(v) for v in factor.values}:
            raise AdaptiveError(f"baseline value outside domain for {factor.name}")
    if max_interaction_order < 2:
        raise AdaptiveError("max_interaction_order must be at least two")
    max_interaction_order = min(max_interaction_order, len(factors))
    if max_retries < 0:
        raise AdaptiveError("max_retries cannot be negative")
    if replicates_per_cell < 1:
        raise AdaptiveError("replicates_per_cell must be at least one")
    if not 0.0 <= exploration_fraction <= 1.0:
        raise AdaptiveError("exploration_fraction must be between zero and one")
    names = {f.name for f in factors}
    normalized_pairs = set()
    for pair in related_pairs:
        if len(pair) != 2 or pair[0] == pair[1] or not set(pair) <= names:
            raise AdaptiveError("related_pairs must contain two distinct declared factors")
        normalized_pairs.add(tuple(sorted(pair)))
    base = dict(baseline)
    singles = []
    for factor in factors:
        for value in factor.values:
            if _canonical(value) != _canonical(base[factor.name]):
                singles.append(_make_candidate(
                    artifact_hash=artifact_hash, context_digest=context_digest,
                    observation_model_digest=observation_model_digest, baseline=base,
                    factor_scope=(factor.name,), factor_levels=((base[factor.name], value),),
                    factor_domains={f.name: f.values for f in factors},
                    replicates_per_cell=replicates_per_cell,
                ))
    pairwise = []
    domains = {f.name: f.values for f in factors}
    for left, right in combinations(factors, 2):
        for levels_left in combinations(left.values, 2):
            for levels_right in combinations(right.values, 2):
                pairwise.append(_make_candidate(
                    artifact_hash=artifact_hash, context_digest=context_digest,
                    observation_model_digest=observation_model_digest, baseline=base,
                    factor_scope=(left.name, right.name),
                    factor_levels=(levels_left, levels_right),
                    factor_domains=domains,
                    replicates_per_cell=replicates_per_cell,
                ))
    singles.sort(key=lambda c: c.digest)
    pairwise.sort(key=lambda c: c.digest)
    plan_identity = {
        "artifact": artifact_hash, "context": context_digest,
        "observation_model": observation_model_digest,
        "baseline": tuple(sorted(base.items())),
        "singles": [c.root_digest for c in singles],
        "pairwise": [c.root_digest for c in pairwise],
        "related_pairs": sorted(normalized_pairs),
        "max_order": max_interaction_order, "max_retries": max_retries,
        "replicates_per_cell": replicates_per_cell,
        "exploration_fraction": exploration_fraction,
    }
    return AdaptivePlan(
        artifact_hash, context_digest, observation_model_digest, factors,
        tuple(sorted(base.items())), tuple(singles), tuple(pairwise),
        frozenset(normalized_pairs), max_interaction_order, max_retries,
        replicates_per_cell, exploration_fraction, _digest(plan_identity),
    )


def _all_singles_completed(plan: AdaptivePlan, ledger: AdaptiveLedger) -> bool:
    return all(c.digest in ledger.records for c in plan.singles)


def _higher_order_candidates(plan: AdaptivePlan, ledger: AdaptiveLedger):
    baseline = dict(plan.baseline)
    generated: dict[str, AdaptiveCandidate] = {}
    for record in ledger.records.values():
        parent = record.candidate
        if record.status != EvidenceStatus.OBSERVED_INTERACTION:
            continue
        scope = parent.factor_scope
        if len(scope) < 2 or len(scope) >= plan.max_interaction_order:
            continue
        remaining = [f for f in plan.factors if f.name not in scope]
        for extra in remaining:
            for extra_levels in combinations(extra.values, 2):
                new_scope = tuple(sorted(scope + (extra.name,)))
                old_levels = dict(zip(scope, parent.factor_levels))
                old_levels[extra.name] = extra_levels
                levels = tuple(old_levels[n] for n in new_scope)
                candidate = _make_candidate(
                    artifact_hash=plan.artifact_hash, context_digest=plan.context_digest,
                    observation_model_digest=plan.observation_model_digest,
                    baseline=baseline, factor_scope=new_scope,
                    factor_levels=levels,
                    factor_domains={f.name: f.values for f in plan.factors},
                    replicates_per_cell=plan.replicates_per_cell,
                    trigger_digests=(parent.digest,),
                )
                previous = generated.get(candidate.root_digest)
                if previous:
                    candidate = AdaptiveCandidate(
                        candidate.artifact_hash, candidate.context_digest,
                        candidate.observation_model_digest, candidate.baseline,
                        candidate.replicates_per_cell, candidate.kind,
                        candidate.factor_scope, candidate.factor_levels,
                        candidate.cells, candidate.targets, candidate.root_digest,
                        candidate.digest, candidate.retry_index,
                        tuple(sorted(set(previous.trigger_digests + candidate.trigger_digests))),
                    )
                generated[candidate.root_digest] = candidate
    return tuple(generated[k] for k in sorted(generated))


def _retry_candidates(plan: AdaptivePlan, ledger: AdaptiveLedger):
    retries = []
    for record in ledger.records.values():
        c = record.candidate
        if record.status != EvidenceStatus.INCONCLUSIVE or c.retry_index >= plan.max_retries:
            continue
        retry = _make_candidate(
            artifact_hash=plan.artifact_hash, context_digest=plan.context_digest,
            observation_model_digest=plan.observation_model_digest,
            baseline=dict(plan.baseline), factor_scope=c.factor_scope,
            factor_levels=c.factor_levels,
            factor_domains={f.name: f.values for f in plan.factors},
            replicates_per_cell=plan.replicates_per_cell,
            retry_index=c.retry_index + 1,
            trigger_digests=c.trigger_digests,
        )
        if retry.digest not in ledger.records:
            retries.append(retry)
    return tuple(retries)


def _single_signal_factors(ledger: AdaptiveLedger) -> set[str]:
    signals = {
        EvidenceStatus.OBSERVED_BEHAVIORAL_INFLUENCE,
        EvidenceStatus.INTERNAL_PATH_CHANGE_ONLY,
        EvidenceStatus.INCONCLUSIVE,
    }
    result = set()
    for record in ledger.records.values():
        if record.candidate.kind == ExperimentKind.SINGLE_INTERVENTION and (
            record.status in signals or record.guidance_tags
        ):
            result.update(record.candidate.factor_scope)
    return result


def _validate_ledger_binding(plan: AdaptivePlan, ledger: AdaptiveLedger) -> None:
    expected_baseline = plan.baseline
    factor_names = {f.name for f in plan.factors}
    for record in ledger.records.values():
        candidate = record.candidate
        if (candidate.artifact_hash, candidate.context_digest,
                candidate.observation_model_digest, candidate.baseline,
                candidate.replicates_per_cell) != (
                plan.artifact_hash, plan.context_digest,
                plan.observation_model_digest, expected_baseline,
                plan.replicates_per_cell):
            raise AdaptiveError("ledger contains evidence from a different pinned plan context")
        if not set(candidate.factor_scope) <= factor_names:
            raise AdaptiveError("ledger candidate references factors outside this plan")


def plan_next_batch(plan: AdaptivePlan, ledger: AdaptiveLedger,
                    execution_budget: int) -> tuple[AdaptiveCandidate, ...]:
    """Choose atomic experiment blocks; budget is measured in execution cells.

    The policy is staged: all single-factor interventions first, then 2x2
    pairwise blocks. Observed interactions trigger higher-order blocks.
    A bounded exploration reserve prevents repeated positive evidence from
    starving unrelated pairs; retries and evidence-linked candidates exploit
    known signals. The budget counts cells and blocks are never split.
    """
    if execution_budget < 0:
        raise AdaptiveError("execution budget cannot be negative")
    _validate_ledger_binding(plan, ledger)
    if execution_budget == 0:
        return ()
    if not _all_singles_completed(plan, ledger):
        pool = [c for c in plan.singles if c.digest not in ledger.records]
        pool.sort(key=lambda c: c.digest)
    else:
        pool = [c for c in plan.pairwise if c.digest not in ledger.records]
        pool.extend(_higher_order_candidates(plan, ledger))
        pool.extend(_retry_candidates(plan, ledger))
        signals = _single_signal_factors(ledger)

        def priority(c):
            if c.retry_index:
                band = 120
            elif len(c.factor_scope) > 2:
                band = 110
            elif tuple(sorted(c.factor_scope)) in plan.related_pairs:
                band = 80
            elif set(c.factor_scope) & signals:
                band = 60
            else:
                band = 30
            novelty = len(c.targets - ledger.executed_targets)
            return (-band, -novelty, c.digest)

        exploit, explore = [], []
        for candidate in pool:
            if (candidate.retry_index or len(candidate.factor_scope) > 2
                    or tuple(sorted(candidate.factor_scope)) in plan.related_pairs
                    or set(candidate.factor_scope) & signals):
                exploit.append(candidate)
            else:
                explore.append(candidate)
        exploit.sort(key=priority)
        explore.sort(key=priority)
        reserve = 0
        if exploit and explore and execution_budget >= 16:
            reserve = min(execution_budget, max(8, int(execution_budget * plan.exploration_fraction)))
        selected, spent = [], 0

        def take(queue, allowance):
            nonlocal spent
            chosen, used = [], 0
            for candidate in queue:
                if candidate.digest not in ledger.records and used + candidate.cell_cost <= allowance:
                    chosen.append(candidate)
                    used += candidate.cell_cost
            selected.extend(chosen)
            spent += used
            return {c.digest for c in chosen}

        chosen_exploit = take(exploit, execution_budget - reserve)
        chosen_explore = take(explore, reserve)
        remaining = [c for c in exploit + explore
                     if c.digest not in chosen_exploit and c.digest not in chosen_explore]
        remaining.sort(key=priority)
        take(remaining, execution_budget - spent)
        return tuple(selected)

    selected, spent = [], 0
    for candidate in pool:
        if spent + candidate.cell_cost <= execution_budget:
            selected.append(candidate)
            spent += candidate.cell_cost
    return tuple(selected)


def adaptive_report(plan: AdaptivePlan, ledger: AdaptiveLedger) -> dict[str, object]:
    _validate_ledger_binding(plan, ledger)
    pending_singles = sum(c.digest not in ledger.records for c in plan.singles)
    pending_pairs = sum(c.digest not in ledger.records for c in plan.pairwise)
    triggered_higher = _higher_order_candidates(plan, ledger)
    pending_higher = sum(c.digest not in ledger.records for c in triggered_higher)
    inconclusive = sum(r.status == EvidenceStatus.INCONCLUSIVE for r in ledger.records.values())
    interactions = sum(r.status == EvidenceStatus.OBSERVED_INTERACTION for r in ledger.records.values())
    latest_by_root = {}
    for record in ledger.records.values():
        previous = latest_by_root.get(record.candidate.root_digest)
        if previous is None or record.candidate.retry_index > previous.candidate.retry_index:
            latest_by_root[record.candidate.root_digest] = record
    pending_retries = sum(
        r.status == EvidenceStatus.INCONCLUSIVE
        and r.candidate.retry_index < plan.max_retries
        for r in latest_by_root.values()
    )
    return {
        "recorded_experiments": len(ledger.records),
        "pending_single_interventions": pending_singles,
        "pending_pairwise_blocks": pending_pairs,
        "triggered_higher_order_blocks": pending_higher,
        "observed_interactions": interactions,
        "inconclusive_experiments": inconclusive,
        "pending_inconclusive_retries": pending_retries,
        "executed_experiment_targets": sorted(ledger.executed_targets),
        "observed_feedback_targets": sorted(ledger.observed_targets),
        "semantic_completeness_claim": False,
    }
