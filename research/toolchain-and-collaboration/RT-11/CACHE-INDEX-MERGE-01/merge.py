"""Reference model for merging immutable cache-result candidates."""

from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256

from cache_index import validate_cache_index
from package_identity import digest


def artifact_id(payload):
    return "sha256:" + sha256(payload).hexdigest()


@dataclass(frozen=True)
class Candidate:
    identity: str
    producer: str
    evidence: str
    determinism: str
    result_status: str
    outputs: tuple[str, ...]


def merge(indexes, components):
    grouped = defaultdict(dict)
    for producer, evidence, index in indexes:
        for record in validate_cache_index(index, components)["records"]:
            key = digest("cache-result-candidate-v1", {"producer": producer, "evidence": evidence, "record": record})
            candidate = Candidate(key, producer, evidence, record["determinism"],
                                  record["status"], tuple(record["output_artifacts"]))
            grouped[record["action_key"]][key] = candidate
    return {key: tuple(rows[identity] for identity in sorted(rows)) for key, rows in sorted(grouped.items())}


def lookup(index, action, *, required_evidence, authorities, verified, artifacts, required_outputs):
    if action not in index:
        return "miss", None
    candidates = [
        row for row in index[action]
        if row.producer in authorities and row.identity in verified and row.evidence == required_evidence
    ]
    if not candidates:
        return "no-applicable-attestation", None
    variants = {(row.result_status, row.outputs) for row in candidates if row.determinism == "byte_deterministic"}
    if not variants:
        return "no-exact-byte-candidate", None
    if len(variants) != 1:
        return "conflict", None
    status, outputs = variants.pop()
    if len(outputs) != required_outputs:
        return "output-shape-mismatch", None
    for identity in outputs:
        payload = artifacts.get(identity)
        if payload is None:
            return "artifact-missing", None
        if artifact_id(payload) != identity:
            return "artifact-integrity-error", None
    return "hit", (status, outputs)
