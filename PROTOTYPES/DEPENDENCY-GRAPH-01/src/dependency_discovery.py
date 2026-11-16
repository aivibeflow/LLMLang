"""Scenario 20: evidence-preserving dependency discovery and classification."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Iterable

class DiscoveryError(ValueError):
    pass

class EvidenceSource(str, Enum):
    EXPLICIT="EXPLICIT"
    STATIC="STATIC"
    DYNAMIC="DYNAMIC"
    SANDBOX="SANDBOX"
    PROOF="PROOF"

class DependencyMeaning(str, Enum):
    SEMANTIC_INPUT="SEMANTIC_INPUT"
    CONTROL_INPUT="CONTROL_INPUT"
    CONFIGURATION="CONFIGURATION"
    TOOLCHAIN="TOOLCHAIN"
    ENVIRONMENT="ENVIRONMENT"
    EXTERNAL_EFFECT="EXTERNAL_EFFECT"
    PROVENANCE_ONLY="PROVENANCE_ONLY"
    INCIDENTAL_ACCESS="INCIDENTAL_ACCESS"
    UNKNOWN="UNKNOWN"

HASH_RELEVANT=frozenset({
    DependencyMeaning.SEMANTIC_INPUT, DependencyMeaning.CONTROL_INPUT,
    DependencyMeaning.CONFIGURATION, DependencyMeaning.TOOLCHAIN,
    DependencyMeaning.ENVIRONMENT, DependencyMeaning.EXTERNAL_EFFECT,
})

class AuditStatus(str, Enum):
    GAP_FOUND="GAP_FOUND"
    REVIEW_REQUIRED="REVIEW_REQUIRED"
    SUPPORTED_WITHIN_SCOPE="SUPPORTED_WITHIN_SCOPE"
    NOT_CHECKED="NOT_CHECKED"

@dataclass(frozen=True)
class DependencyObservation:
    artifact_hash: str
    input_hash: str
    source: EvidenceSource
    tool_id: str
    scope: str
    evidence_digest: str

    def __post_init__(self):
        if not all((self.artifact_hash,self.input_hash,self.tool_id,self.scope,self.evidence_digest)):
            raise DiscoveryError("observation identities and evidence are required")

@dataclass(frozen=True)
class CandidateDependency:
    input_hash: str
    sources: tuple[EvidenceSource,...]
    tool_ids: tuple[str,...]
    evidence_digests: tuple[str,...]
    meaning: DependencyMeaning

@dataclass(frozen=True)
class DependencyAudit:
    artifact_hash: str
    scope: str
    status: AuditStatus
    declared_dependencies: tuple[str,...]
    semantic_dependencies: tuple[str,...]
    missing_dependencies: tuple[str,...]
    unresolved_candidates: tuple[str,...]
    candidates: tuple[CandidateDependency,...]
    evidence_digest: str
    reason: str

def _digest(payload):
    encoded=json.dumps(payload,sort_keys=True,separators=(",",":"))
    return sha256(encoded.encode("utf-8")).hexdigest()

def discover_candidates(artifact_hash: str, scope: str,
                        observations: Iterable[DependencyObservation],
                        decisions: dict[str,DependencyMeaning]) -> tuple[CandidateDependency,...]:
    grouped={}
    for item in observations:
        if item.artifact_hash!=artifact_hash or item.scope!=scope:
            raise DiscoveryError("observation is bound to a different artifact or scope")
        grouped.setdefault(item.input_hash,[]).append(item)
    candidates=[]
    for input_hash,rows in sorted(grouped.items()):
        meaning=decisions.get(input_hash,DependencyMeaning.UNKNOWN)
        if not isinstance(meaning,DependencyMeaning):
            raise DiscoveryError(f"invalid dependency classification for {input_hash}")
        candidates.append(CandidateDependency(
            input_hash,
            tuple(sorted({r.source for r in rows},key=lambda x:x.value)),
            tuple(sorted({r.tool_id for r in rows})),
            tuple(sorted({r.evidence_digest for r in rows})),
            meaning,
        ))
    unknown=set(decisions)-set(grouped)
    if unknown:
        raise DiscoveryError("classification supplied without discovery evidence: "+", ".join(sorted(unknown)))
    return tuple(candidates)

def audit_dependencies(artifact_hash: str, scope: str,
                       declared_dependencies: Iterable[str],
                       observations: Iterable[DependencyObservation],
                       decisions: dict[str,DependencyMeaning]) -> DependencyAudit:
    if not artifact_hash or not scope:
        raise DiscoveryError("artifact and scope are required")
    rows=tuple(observations)
    declared=tuple(sorted(set(declared_dependencies)))
    if not rows:
        digest=_digest({"artifact":artifact_hash,"scope":scope,"declared":declared,
                        "observations":[],"decisions":{}})
        return DependencyAudit(artifact_hash,scope,AuditStatus.NOT_CHECKED,
            declared,(),(),(),(),digest,"no dependency discovery evidence was supplied")
    candidates=discover_candidates(artifact_hash,scope,rows,decisions)
    semantic=tuple(sorted(c.input_hash for c in candidates if c.meaning in HASH_RELEVANT))
    unresolved=tuple(sorted(c.input_hash for c in candidates if c.meaning is DependencyMeaning.UNKNOWN))
    missing=tuple(sorted(set(semantic)-set(declared)))
    evidence_payload={
        "artifact":artifact_hash,"scope":scope,"declared":declared,
        "candidates":[(c.input_hash,[s.value for s in c.sources],c.tool_ids,
                       c.evidence_digests,c.meaning.value) for c in candidates],
    }
    digest=_digest(evidence_payload)
    if missing:
        status=AuditStatus.GAP_FOUND
        reason="classified hash-relevant candidates are absent from declarations"
    elif unresolved:
        status=AuditStatus.REVIEW_REQUIRED
        reason="one or more discovered candidates have unresolved semantic meaning"
    else:
        status=AuditStatus.SUPPORTED_WITHIN_SCOPE
        reason="no classified gap or unresolved candidate was found in supplied evidence; not a global completeness proof"
    return DependencyAudit(artifact_hash,scope,status,declared,semantic,missing,
                           unresolved,candidates,digest,reason)
