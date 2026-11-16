"""Scenario 23: controlled multi-factor and 2x2 factorial analysis."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from hashlib import sha256
from itertools import product
import json
from typing import Iterable, Mapping

class MultiFactorError(ValueError): pass
class CellSide(str, Enum):
    BASELINE="BASELINE"
    TREATMENT="TREATMENT"
class MultiFactorStatus(str, Enum):
    OBSERVED_BEHAVIORAL_INFLUENCE="OBSERVED_BEHAVIORAL_INFLUENCE"
    INTERNAL_PATH_CHANGE_ONLY="INTERNAL_PATH_CHANGE_ONLY"
    NO_OBSERVED_DIFFERENCE="NO_OBSERVED_DIFFERENCE"
    OBSERVED_INTERACTION="OBSERVED_INTERACTION"
    NO_INTERACTION_OBSERVED="NO_INTERACTION_OBSERVED"
    INCONCLUSIVE="INCONCLUSIVE"

def _canonical(value):
    def encode(item):
        if isinstance(item, Enum): return item.value
        raise TypeError(type(item).__name__)
    try:
        return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,
                          allow_nan=False,default=encode)
    except (TypeError,ValueError) as exc:
        raise MultiFactorError(f"non-canonical JSON value: {exc}") from exc

def _digest(value):
    return sha256(_canonical(value).encode()).hexdigest()

def _validate_assignment(items):
    names=[name for name,_ in items]
    if not names or any(not n for n in names) or len(names)!=len(set(names)):
        raise MultiFactorError("assignment needs unique non-empty factor names")
    if tuple(sorted(items))!=items:
        raise MultiFactorError("assignment must be sorted by factor name")
    for _,value in items: _canonical(value)

def assignment(values: Mapping[str,object]):
    result=tuple(sorted(values.items()))
    _validate_assignment(result)
    return result

def _evidence(identity,rows,status,reason):
    return _digest({"identity":identity,
        "runs":sorted(_canonical(row.__dict__) for row in rows),
        "status":status.value,"reason":reason})

@dataclass(frozen=True)
class MultiFactorRun:
    artifact_hash:str
    context_digest:str
    observation_model_digest:str
    baseline_assignment:tuple[tuple[str,object],...]
    treatment_assignment:tuple[tuple[str,object],...]
    side:CellSide
    pair_index:int
    input_digest:str
    observable_value:object
    trace_digest:str
    run_digest:str
    def __post_init__(self):
        if not all((self.artifact_hash,self.context_digest,self.observation_model_digest,
                    self.input_digest,self.trace_digest,self.run_digest)):
            raise MultiFactorError("run identities and digests are required")
        if self.pair_index<0: raise MultiFactorError("pair_index must be non-negative")
        _validate_assignment(self.baseline_assignment); _validate_assignment(self.treatment_assignment)
        if set(dict(self.baseline_assignment))!=set(dict(self.treatment_assignment)):
            raise MultiFactorError("baseline and treatment factor sets differ")
        if self.baseline_assignment==self.treatment_assignment:
            raise MultiFactorError("treatment must differ from baseline")
        _canonical(self.observable_value)

@dataclass(frozen=True)
class MultiFactorResult:
    status:MultiFactorStatus
    changed_factors:tuple[str,...]
    pair_count:int
    baseline_input_digest:str|None
    treatment_input_digest:str|None
    baseline_observable_digest:str|None
    treatment_observable_digest:str|None
    evidence_digest:str
    reason:str

def analyze_joint_intervention(artifact_hash,context_digest,observation_model_digest,
        baseline:Mapping[str,object],treatment:Mapping[str,object],
        runs:Iterable[MultiFactorRun],min_pairs:int=2)->MultiFactorResult:
    if not all((artifact_hash,context_digest,observation_model_digest)):
        raise MultiFactorError("experiment identity fields are required")
    if min_pairs<1: raise MultiFactorError("min_pairs must be at least one")
    base,treat=assignment(baseline),assignment(treatment)
    if set(dict(base))!=set(dict(treat)):
        raise MultiFactorError("baseline and treatment factor sets differ")
    tv=dict(treat)
    changed=tuple(n for n,v in base if _canonical(v)!=_canonical(tv[n]))
    if not changed: raise MultiFactorError("treatment must change at least one factor")
    rows=tuple(runs)
    identity={"artifact":artifact_hash,"context":context_digest,"observation_model":observation_model_digest,
              "baseline":base,"treatment":treat,"min_pairs":min_pairs}
    def finish(status,reason,count=0,bi=None,ti=None,bo=None,to=None):
        return MultiFactorResult(status,changed,count,bi,ti,bo,to,_evidence(identity,rows,status,reason),reason)
    if not rows: return finish(MultiFactorStatus.INCONCLUSIVE,"no execution evidence supplied")
    grouped={}
    for row in rows:
        if (row.artifact_hash,row.context_digest,row.observation_model_digest,
            row.baseline_assignment,row.treatment_assignment)!=(artifact_hash,context_digest,
            observation_model_digest,base,treat):
            return finish(MultiFactorStatus.INCONCLUSIVE,"run bound to a different artifact, context, model, or intervention")
        pair=grouped.setdefault(row.pair_index,{})
        if row.side in pair: return finish(MultiFactorStatus.INCONCLUSIVE,"duplicate side in a paired trial")
        pair[row.side]=row
    if len(grouped)<min_pairs: return finish(MultiFactorStatus.INCONCLUSIVE,"insufficient paired trials",len(grouped))
    if any(set(p)!={CellSide.BASELINE,CellSide.TREATMENT} for p in grouped.values()):
        return finish(MultiFactorStatus.INCONCLUSIVE,"one or more pairs are incomplete",len(grouped))
    pairs=[grouped[k] for k in sorted(grouped)]
    bi={p[CellSide.BASELINE].input_digest for p in pairs}
    ti={p[CellSide.TREATMENT].input_digest for p in pairs}
    if len(bi)!=1 or len(ti)!=1:
        return finish(MultiFactorStatus.INCONCLUSIVE,"input configurations drifted across pairs",len(pairs))
    bi,ti=next(iter(bi)),next(iter(ti))
    if bi==ti: return finish(MultiFactorStatus.INCONCLUSIVE,"baseline and treatment input digests match",len(pairs),bi,ti)
    bo={_canonical(p[CellSide.BASELINE].observable_value) for p in pairs}
    to={_canonical(p[CellSide.TREATMENT].observable_value) for p in pairs}
    bt={p[CellSide.BASELINE].trace_digest for p in pairs}
    tt={p[CellSide.TREATMENT].trace_digest for p in pairs}
    if any(len(s)!=1 for s in (bo,to,bt,tt)):
        return finish(MultiFactorStatus.INCONCLUSIVE,"observable outcomes or traces are unstable",len(pairs),bi,ti)
    bo,to=next(iter(bo)),next(iter(to))
    if bo!=to: status,reason=MultiFactorStatus.OBSERVED_BEHAVIORAL_INFLUENCE,"joint intervention changes observable behavior"
    elif next(iter(bt))!=next(iter(tt)): status,reason=MultiFactorStatus.INTERNAL_PATH_CHANGE_ONLY,"observables match but traces differ"
    else: status,reason=MultiFactorStatus.NO_OBSERVED_DIFFERENCE,"no difference observed for this joint intervention and pinned context"
    return finish(status,reason,len(pairs),bi,ti,bo,to)

@dataclass(frozen=True)
class FactorialCellRun:
    artifact_hash:str
    context_digest:str
    observation_model_digest:str
    factor_a:str
    factor_b:str
    level_a:object
    level_b:object
    context_assignment:tuple[tuple[str,object],...]
    pair_index:int
    input_digest:str
    observable_value:object
    trace_digest:str
    run_digest:str
    def __post_init__(self):
        if not all((self.artifact_hash,self.context_digest,self.observation_model_digest,
                    self.factor_a,self.factor_b,self.input_digest,self.trace_digest,self.run_digest)):
            raise MultiFactorError("factorial run identities and digests are required")
        if self.factor_a==self.factor_b: raise MultiFactorError("factorial factors must be distinct")
        if self.pair_index<0: raise MultiFactorError("pair_index must be non-negative")
        _validate_assignment(self.context_assignment)
        if {self.factor_a,self.factor_b}&set(dict(self.context_assignment)):
            raise MultiFactorError("factorial factors must not appear in pinned context")
        _canonical(self.level_a); _canonical(self.level_b); _canonical(self.observable_value)

@dataclass(frozen=True)
class InteractionResult:
    status:MultiFactorStatus
    factor_a:str
    factor_b:str
    pair_count:int
    simple_effect_a_when_b0:bool|None
    simple_effect_a_when_b1:bool|None
    simple_effect_b_when_a0:bool|None
    simple_effect_b_when_a1:bool|None
    numeric_interaction_contrast:str|None
    evidence_digest:str
    reason:str

def analyze_pairwise_interaction(artifact_hash,context_digest,observation_model_digest,
        factor_a,levels_a,factor_b,levels_b,context_assignment,runs,min_pairs=2)->InteractionResult:
    if not all((artifact_hash,context_digest,observation_model_digest,factor_a,factor_b)):
        raise MultiFactorError("factorial identity fields are required")
    if factor_a==factor_b or len(levels_a)!=2 or len(levels_b)!=2:
        raise MultiFactorError("two distinct factors and exactly two levels each are required")
    if _canonical(levels_a[0])==_canonical(levels_a[1]) or _canonical(levels_b[0])==_canonical(levels_b[1]):
        raise MultiFactorError("factor levels must be distinct")
    if min_pairs<1: raise MultiFactorError("min_pairs must be at least one")
    pinned=assignment(context_assignment)
    if {factor_a,factor_b}&set(dict(pinned)): raise MultiFactorError("factorial factors cannot be pinned context variables")
    rows=tuple(runs)
    identity={"artifact":artifact_hash,"context":context_digest,"observation_model":observation_model_digest,
              "factor_a":factor_a,"levels_a":levels_a,"factor_b":factor_b,"levels_b":levels_b,
              "context_assignment":pinned,"min_pairs":min_pairs}
    def finish(status,reason,count=0,effects=(None,None,None,None),contrast=None):
        return InteractionResult(status,factor_a,factor_b,count,*effects,contrast,
                                 _evidence(identity,rows,status,reason),reason)
    if not rows: return finish(MultiFactorStatus.INCONCLUSIVE,"no factorial execution evidence supplied")
    expected=set(product(range(2),range(2))); grouped={}
    for row in rows:
        if (row.artifact_hash,row.context_digest,row.observation_model_digest,row.factor_a,row.factor_b,
            row.context_assignment)!=(artifact_hash,context_digest,observation_model_digest,factor_a,factor_b,pinned):
            return finish(MultiFactorStatus.INCONCLUSIVE,"run bound to a different context or factorial design")
        try:
            i=next(i for i,v in enumerate(levels_a) if _canonical(v)==_canonical(row.level_a))
            j=next(j for j,v in enumerate(levels_b) if _canonical(v)==_canonical(row.level_b))
        except StopIteration: return finish(MultiFactorStatus.INCONCLUSIVE,"undeclared factor level")
        pair=grouped.setdefault(row.pair_index,{})
        if (i,j) in pair: return finish(MultiFactorStatus.INCONCLUSIVE,"duplicate factorial cell")
        pair[(i,j)]=row
    if len(grouped)<min_pairs: return finish(MultiFactorStatus.INCONCLUSIVE,"insufficient factorial trials",len(grouped))
    if any(set(p)!=expected for p in grouped.values()):
        return finish(MultiFactorStatus.INCONCLUSIVE,"one or more factorial trials lack a cell",len(grouped))
    blocks=[grouped[k] for k in sorted(grouped)]; values={}; inputs={}
    for cell in expected:
        outcomes={_canonical(b[cell].observable_value) for b in blocks}
        traces={b[cell].trace_digest for b in blocks}
        digests={b[cell].input_digest for b in blocks}
        if any(len(s)!=1 for s in (outcomes,traces,digests)):
            return finish(MultiFactorStatus.INCONCLUSIVE,f"outcome, trace, or input drift in cell {cell}",len(blocks))
        values[cell]=blocks[0][cell].observable_value; inputs[cell]=next(iter(digests))
    if len(set(inputs.values()))!=4:
        return finish(MultiFactorStatus.INCONCLUSIVE,"each factorial cell must have a distinct input digest",len(blocks))
    o00,o10,o01,o11=(values[(0,0)],values[(1,0)],values[(0,1)],values[(1,1)])
    effects=(_canonical(o00)!=_canonical(o10),_canonical(o01)!=_canonical(o11),
             _canonical(o00)!=_canonical(o01),_canonical(o10)!=_canonical(o11))
    numeric=all(type(v) in (int,float) for v in (o00,o10,o01,o11)); contrast=None
    if numeric:
        try: d=(Decimal(str(o11))-Decimal(str(o10)))-(Decimal(str(o01))-Decimal(str(o00)))
        except InvalidOperation: return finish(MultiFactorStatus.INCONCLUSIVE,"invalid numeric contrast",len(blocks),effects)
        contrast=str(d); interaction=d!=0
        reason="non-zero numeric difference-in-differences" if interaction else "numeric difference-in-differences is zero"
    else:
        interaction=effects[0]!=effects[1] or effects[2]!=effects[3]
        reason="conditional categorical effect differs across levels" if interaction else "no conditional categorical effect pattern detected"
    status=MultiFactorStatus.OBSERVED_INTERACTION if interaction else MultiFactorStatus.NO_INTERACTION_OBSERVED
    return finish(status,reason,len(blocks),effects,contrast)
