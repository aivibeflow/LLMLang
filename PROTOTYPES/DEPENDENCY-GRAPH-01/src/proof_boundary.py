"""Content-addressed evidence envelope; solver answers are not proofs by themselves."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib, json
from typing import Any, Mapping
from .typed_ir import TypedProgram
from .formal_core import execute

ENCODER_VERSION="smtlib-relational-encoder/1"
OBSERVATION_CONTRACT_VERSION="return+selected-state/1"
def sha256(data:bytes)->str: return hashlib.sha256(data).hexdigest()
def canonical_digest(value:Any)->str:
    return sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode())
def _valid_digest(value:str)->bool:
    return isinstance(value,str) and len(value)==64 and all(c in "0123456789abcdef" for c in value)

@dataclass(frozen=True)
class SolverIdentity:
    name:str
    version:str
    executable_sha256:str
    command:tuple[str,...]
    options:tuple[tuple[str,str],...]=()
    def __post_init__(self):
        if not self.name or not self.version or not _valid_digest(self.executable_sha256):
            raise ValueError("solver identity must include name, version and executable SHA-256")

@dataclass(frozen=True)
class ProofCheckReceipt:
    query_sha256:str
    proof_sha256:str
    checker_name:str
    checker_version:str
    valid:bool
    def __post_init__(self):
        if not _valid_digest(self.query_sha256) or not _valid_digest(self.proof_sha256):
            raise ValueError("proof receipt digests must be SHA-256 hex")
        if not self.checker_name or not self.checker_version:
            raise ValueError("proof checker identity is required")

@dataclass(frozen=True)
class EvidenceRecord:
    status:str
    typed_ir_sha256:str
    semantics_version:str
    validator_version:str
    validator_sha256:str
    encoder_version:str
    encoder_sha256:str
    observation_contract_version:str
    observation_dimensions:tuple[str,...]
    query_sha256:str
    solver:SolverIdentity
    solver_result:str
    proof_sha256:str|None
    checker_name:str|None
    checker_version:str|None
    record_sha256:str

def create_evidence_record(typed:TypedProgram,smt_query:str,solver:SolverIdentity,
                           solver_result:str,validator_sha256:str,encoder_sha256:str,
                           proof_receipt:ProofCheckReceipt|None=None)->EvidenceRecord:
    if solver_result not in ("sat","unsat","unknown"): raise ValueError("invalid solver result")
    if not _valid_digest(validator_sha256) or not _valid_digest(encoder_sha256):
        raise ValueError("toolchain source digests must be SHA-256 hex")
    qhash=sha256(smt_query.encode())
    if proof_receipt and (proof_receipt.query_sha256!=qhash or not proof_receipt.valid or solver_result!="unsat"):
        raise ValueError("proof receipt does not validate this UNSAT query")
    if solver_result=="sat": status="SOLVER_REPORTED_SAT_COUNTEREXAMPLE_UNCHECKED"
    elif solver_result=="unsat": status="UNAUTHENTICATED_CHECKER_RECEIPT_PRESENT" if proof_receipt else "SOLVER_REPORTED_UNSAT_UNCHECKED"
    else: status="UNKNOWN"
    dimensions=("outcome","return",*(f"state:{x}" for x in typed.observable_state))
    payload={"status":status,"typed_ir_sha256":typed.ir_digest,"semantics_version":typed.semantics_version,
      "validator_version":typed.validator_version,"validator_sha256":validator_sha256,
      "encoder_version":ENCODER_VERSION,"encoder_sha256":encoder_sha256,
      "observation_contract_version":OBSERVATION_CONTRACT_VERSION,"observation_dimensions":dimensions,
      "query_sha256":qhash,"solver":solver.__dict__,"solver_result":solver_result,
      "proof_sha256":proof_receipt.proof_sha256 if proof_receipt else None,
      "checker_name":proof_receipt.checker_name if proof_receipt else None,
      "checker_version":proof_receipt.checker_version if proof_receipt else None}
    return EvidenceRecord(status,typed.ir_digest,typed.semantics_version,typed.validator_version,
      validator_sha256,ENCODER_VERSION,encoder_sha256,OBSERVATION_CONTRACT_VERSION,dimensions,qhash,
      solver,solver_result,payload["proof_sha256"],payload["checker_name"],payload["checker_version"],canonical_digest(payload))

def validate_counterexample(typed:TypedProgram,factor:str,left:Mapping[str,Any],right:Mapping[str,Any],
                            initial_state:Mapping[str,Any],input_types:Mapping[str,str])->str:
    """Replay a SAT model; only a real pair of differing observations is confirmed."""
    expected_state=tuple(sorted((k,{"Int":"int","Bool":"bool","String":"str"}[t]) for k,t in typed.initial_state_types))
    actual_state=tuple(sorted((k,type(v).__name__) for k,v in initial_state.items()))
    if tuple(sorted(input_types.items()))!=typed.input_types or actual_state!=expected_state:
        return "COUNTEREXAMPLE_REJECTED"
    if factor not in input_types or set(left)!=set(input_types) or set(right)!=set(input_types):
        return "COUNTEREXAMPLE_REJECTED"
    for name,sort in input_types.items():
        def matches(v):
            return ((sort=="Bool" and type(v) is bool) or (sort=="Int" and type(v) is int) or
                    (sort=="String" and isinstance(v,str)))
        if not matches(left[name]) or not matches(right[name]): return "COUNTEREXAMPLE_REJECTED"
        if name!=factor and left[name]!=right[name]: return "COUNTEREXAMPLE_REJECTED"
    if left[factor]==right[factor]: return "COUNTEREXAMPLE_REJECTED"
    try:
        lo=execute(typed.program,left,initial_state,typed.observable_state)
        ro=execute(typed.program,right,initial_state,typed.observable_state)
    except Exception: return "COUNTEREXAMPLE_REJECTED"
    return "COUNTEREXAMPLE_CONFIRMED_BY_REFERENCE_EVALUATOR" if lo!=ro else "COUNTEREXAMPLE_REJECTED"
