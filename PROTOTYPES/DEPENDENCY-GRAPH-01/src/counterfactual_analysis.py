"""Scenario 21: controlled counterfactual comparison of observable behavior.

Consumes normalized run records. It does not execute programs or prove non-dependence.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Iterable

class ExperimentError(ValueError):
    pass

class RunSide(str, Enum):
    BASELINE = "BASELINE"
    TREATMENT = "TREATMENT"

class ExperimentStatus(str, Enum):
    OBSERVED_BEHAVIORAL_INFLUENCE = "OBSERVED_BEHAVIORAL_INFLUENCE"
    INTERNAL_PATH_CHANGE_ONLY = "INTERNAL_PATH_CHANGE_ONLY"
    NO_OBSERVED_DIFFERENCE = "NO_OBSERVED_DIFFERENCE"
    INCONCLUSIVE = "INCONCLUSIVE"

@dataclass(frozen=True)
class ExperimentRun:
    artifact_hash: str
    context_digest: str
    observation_model_digest: str
    factor: str
    changed_factors: tuple[str, ...]
    side: RunSide
    pair_index: int
    input_digest: str
    observable_digest: str
    trace_digest: str
    run_digest: str

    def __post_init__(self):
        if not all((self.artifact_hash,self.context_digest,self.observation_model_digest,
                    self.factor,self.input_digest,self.observable_digest,
                    self.trace_digest,self.run_digest)):
            raise ExperimentError("run identities and digests are required")
        if self.pair_index < 0:
            raise ExperimentError("pair_index must be non-negative")

@dataclass(frozen=True)
class CounterfactualResult:
    artifact_hash: str
    context_digest: str
    observation_model_digest: str
    factor: str
    status: ExperimentStatus
    pair_count: int
    baseline_input_digest: str | None
    treatment_input_digest: str | None
    evidence_digest: str
    reason: str

def _digest(payload):
    encoded=json.dumps(payload,sort_keys=True,separators=(",",":"))
    return sha256(encoded.encode("utf-8")).hexdigest()

def analyze_counterfactual(artifact_hash: str, context_digest: str,
                           observation_model_digest: str, factor: str,
                           runs: Iterable[ExperimentRun],
                           min_pairs: int = 2) -> CounterfactualResult:
    if not all((artifact_hash,context_digest,observation_model_digest,factor)):
        raise ExperimentError("experiment identity fields are required")
    if min_pairs < 1:
        raise ExperimentError("min_pairs must be at least one")
    rows=tuple(runs)

    def result(status,reason,pairs=0,baseline=None,treatment=None):
        evidence=_digest({
            "artifact":artifact_hash,"context":context_digest,
            "observation_model":observation_model_digest,"factor":factor,
            "min_pairs":min_pairs,
            "runs":sorted((r.run_digest,r.artifact_hash,r.context_digest,
                           r.observation_model_digest,r.factor,r.changed_factors,
                           r.side.value,r.pair_index,r.input_digest,
                           r.observable_digest,r.trace_digest) for r in rows),
            "status":status.value,"reason":reason,
        })
        return CounterfactualResult(artifact_hash,context_digest,
            observation_model_digest,factor,status,pairs,baseline,treatment,evidence,reason)

    if not rows:
        return result(ExperimentStatus.INCONCLUSIVE,"no execution evidence supplied")
    for row in rows:
        if (row.artifact_hash!=artifact_hash or row.context_digest!=context_digest
                or row.observation_model_digest!=observation_model_digest or row.factor!=factor):
            return result(ExperimentStatus.INCONCLUSIVE,
                "run is bound to a different artifact, context, observation model, or factor")
        if row.changed_factors!=(factor,):
            return result(ExperimentStatus.INCONCLUSIVE,
                "prototype requires exactly the declared single changed factor")

    grouped={}
    for row in rows:
        pair=grouped.setdefault(row.pair_index,{})
        if row.side in pair:
            return result(ExperimentStatus.INCONCLUSIVE,"duplicate run side in a pair")
        pair[row.side]=row
    if len(grouped)<min_pairs:
        return result(ExperimentStatus.INCONCLUSIVE,"insufficient paired trials",len(grouped))
    if any(set(pair)!={RunSide.BASELINE,RunSide.TREATMENT} for pair in grouped.values()):
        return result(ExperimentStatus.INCONCLUSIVE,"one or more trial pairs are incomplete",len(grouped))

    pairs=[grouped[i] for i in sorted(grouped)]
    baseline_inputs={p[RunSide.BASELINE].input_digest for p in pairs}
    treatment_inputs={p[RunSide.TREATMENT].input_digest for p in pairs}
    if len(baseline_inputs)!=1 or len(treatment_inputs)!=1:
        return result(ExperimentStatus.INCONCLUSIVE,
            "input configurations changed across repeated pairs",len(pairs))
    baseline_input=next(iter(baseline_inputs))
    treatment_input=next(iter(treatment_inputs))
    if baseline_input==treatment_input:
        return result(ExperimentStatus.INCONCLUSIVE,
            "baseline and treatment input digests must differ",len(pairs),baseline_input,treatment_input)

    baseline_outcomes={p[RunSide.BASELINE].observable_digest for p in pairs}
    treatment_outcomes={p[RunSide.TREATMENT].observable_digest for p in pairs}
    if len(baseline_outcomes)!=1 or len(treatment_outcomes)!=1:
        return result(ExperimentStatus.INCONCLUSIVE,
            "observable outcomes are unstable across repeated runs",
            len(pairs),baseline_input,treatment_input)
    baseline_traces={p[RunSide.BASELINE].trace_digest for p in pairs}
    treatment_traces={p[RunSide.TREATMENT].trace_digest for p in pairs}
    if len(baseline_traces)!=1 or len(treatment_traces)!=1:
        return result(ExperimentStatus.INCONCLUSIVE,
            "execution traces are unstable across repeated runs",
            len(pairs),baseline_input,treatment_input)

    baseline_outcome=next(iter(baseline_outcomes))
    treatment_outcome=next(iter(treatment_outcomes))
    baseline_trace=next(iter(baseline_traces))
    treatment_trace=next(iter(treatment_traces))
    if baseline_outcome!=treatment_outcome:
        status=ExperimentStatus.OBSERVED_BEHAVIORAL_INFLUENCE
        reason="repeated paired trials show different observable outcomes"
    elif baseline_trace!=treatment_trace:
        status=ExperimentStatus.INTERNAL_PATH_CHANGE_ONLY
        reason="observable outcomes match but execution traces differ"
    else:
        status=ExperimentStatus.NO_OBSERVED_DIFFERENCE
        reason="no difference observed within the tested intervention and context"
    return result(status,reason,len(pairs),baseline_input,treatment_input)
