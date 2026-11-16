"""Immutable contract-to-implementation binding snapshots (experimental)."""
from __future__ import annotations
from dataclasses import dataclass
import json
from typing import Mapping
from .semantic_graph import ContentStore, canonical_bytes, digest

class BindingError(ValueError):
    pass

@dataclass(frozen=True, order=True)
class Binding:
    key: str
    contract_hash: str
    implementation_hash: str
    def record(self):
        return {"key": self.key, "contract_hash": self.contract_hash,
                "implementation_hash": self.implementation_hash}

@dataclass(frozen=True)
class BindingSnapshot:
    root_hash: str
    bindings: tuple[Binding, ...]
    parent_roots: tuple[str, ...] = ()
    def resolve(self, key: str, expected_contract_hash: str) -> str:
        matches = [b for b in self.bindings if b.key == key]
        if not matches:
            raise BindingError(f"no binding for key: {key}")
        if matches[0].contract_hash != expected_contract_hash:
            raise BindingError("binding contract does not match caller contract")
        return matches[0].implementation_hash

def make_binding_snapshot(store: ContentStore,
                          bindings: Mapping[str, tuple[str, str]],
                          parent_roots: tuple[str, ...] = ()) -> BindingSnapshot:
    rows=[]
    for key,(contract_hash,implementation_hash) in bindings.items():
        if not key: raise BindingError("binding key must not be empty")
        try:
            contract=store.get(contract_hash); impl=store.get(implementation_hash)
        except KeyError as exc: raise BindingError("unknown semantic value") from exc
        if contract.kind != "contract": raise BindingError("target must be a contract")
        if impl.kind != "implementation": raise BindingError("source must be an implementation")
        if not any(d.relation=="implements" and d.target_hash==contract_hash
                   and d.hash_relevant for d in impl.dependencies):
            raise BindingError("implementation does not declare this contract")
        rows.append(Binding(key,contract_hash,implementation_hash))
    ordered=tuple(sorted(rows)); parents=tuple(sorted(set(parent_roots)))
    root=digest({"domain":"llmlang.binding-snapshot.v1",
                 "bindings":[b.record() for b in ordered],"parents":parents})
    return BindingSnapshot(root,ordered,parents)

def binding_verification_key(base_verification_key: str,
                             binding_snapshot_root: str) -> str:
    return digest({"domain":"llmlang.binding-verification-key.v1",
                  "base_verification_key":base_verification_key,
                  "binding_snapshot_root":binding_snapshot_root})

def dumps_binding_snapshot(snapshot: BindingSnapshot) -> bytes:
    payload={"format":"llmlang.binding-snapshot","schema_version":1,
             "root_hash":snapshot.root_hash,
             "bindings":[b.record() for b in snapshot.bindings],
             "parent_roots":list(snapshot.parent_roots)}
    return canonical_bytes({"payload":payload,"checksum":digest(payload)})+b"\n"

def loads_binding_snapshot(data: bytes | str, store: ContentStore) -> BindingSnapshot:
    try:
        env=json.loads(data); p=env["payload"]
    except (TypeError,ValueError,KeyError) as exc:
        raise BindingError("invalid binding snapshot") from exc
    if p.get("format")!="llmlang.binding-snapshot" or p.get("schema_version")!=1:
        raise BindingError("unsupported binding snapshot format/schema")
    if digest(p)!=env.get("checksum"): raise BindingError("checksum mismatch")
    try:
        rows={}
        for row in p["bindings"]:
            if row["key"] in rows: raise BindingError("duplicate binding key")
            rows[row["key"]]=(row["contract_hash"],row["implementation_hash"])
        result=make_binding_snapshot(store,rows,tuple(p.get("parent_roots",())))
    except (KeyError,TypeError,ValueError) as exc:
        if isinstance(exc,BindingError): raise
        raise BindingError("malformed binding snapshot") from exc
    if result.root_hash!=p.get("root_hash"): raise BindingError("root hash mismatch")
    return result
