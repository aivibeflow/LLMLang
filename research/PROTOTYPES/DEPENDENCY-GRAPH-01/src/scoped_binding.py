"""Experimental project/tenant/request scoped implementation binding resolver."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from .semantic_graph import ContentStore, digest


class ScopedBindingError(ValueError):
    pass


@dataclass(frozen=True, order=True)
class ScopedBinding:
    key: str
    contract_hash: str
    implementation_hash: str


@dataclass(frozen=True)
class BindingLayer:
    scope: str
    scope_id_hash: str
    snapshot_root: str
    bindings: tuple[ScopedBinding, ...]


@dataclass(frozen=True)
class BindingPolicy:
    precedence: tuple[str, ...]
    allowed_overrides: tuple[tuple[str, str], ...]
    policy_hash: str

    @classmethod
    def create(cls, precedence=("project", "tenant", "request"),
               allowed_overrides=(("project", "tenant"),
                                  ("project", "request"),
                                  ("tenant", "request"))):
        order = tuple(precedence)
        pairs = tuple(sorted(set(tuple(pair) for pair in allowed_overrides)))
        if not order or len(order) != len(set(order)):
            raise ScopedBindingError("precedence must contain unique scopes")
        if any(a not in order or b not in order or order.index(a) >= order.index(b)
               for a, b in pairs):
            raise ScopedBindingError("override pair must follow precedence order")
        root = digest({"domain": "llmlang.binding-policy.v1",
                       "precedence": order, "allowed_overrides": pairs})
        return cls(order, pairs, root)


@dataclass(frozen=True)
class ResolvedBinding:
    root_hash: str
    key: str
    contract_hash: str
    implementation_hash: str
    winning_scope: str
    winning_scope_id_hash: str
    policy_hash: str
    consulted_layers: tuple[tuple[str, str, str], ...]
    resolver_version: str = "scoped-binding-resolver.v1"


def _validate_hash(label: str, value: str) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise ScopedBindingError(f"{label} must be a SHA-256 hex digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ScopedBindingError(f"{label} must be a SHA-256 hex digest") from exc


def resolve_scoped_binding(store: ContentStore, key: str,
                           expected_contract_hash: str,
                           layers: Iterable[BindingLayer],
                           policy: BindingPolicy) -> ResolvedBinding:
    if not key:
        raise ScopedBindingError("binding key must not be empty")
    _validate_hash("expected_contract_hash", expected_contract_hash)
    by_scope = {}
    for layer in layers:
        if layer.scope not in policy.precedence:
            raise ScopedBindingError(f"scope not present in policy: {layer.scope}")
        if layer.scope in by_scope:
            raise ScopedBindingError(f"duplicate scope layer: {layer.scope}")
        _validate_hash("scope_id_hash", layer.scope_id_hash)
        _validate_hash("snapshot_root", layer.snapshot_root)
        row_keys = [row.key for row in layer.bindings]
        if len(row_keys) != len(set(row_keys)):
            raise ScopedBindingError(f"duplicate binding key in {layer.scope} layer")
        by_scope[layer.scope] = layer

    ordered_layers = [by_scope[s] for s in policy.precedence if s in by_scope]
    matches, consulted = [], []
    for layer in ordered_layers:
        consulted.append((layer.scope, layer.scope_id_hash, layer.snapshot_root))
        row = next((item for item in layer.bindings if item.key == key), None)
        if row is None:
            continue
        if row.contract_hash != expected_contract_hash:
            raise ScopedBindingError(
                f"contract mismatch in {layer.scope} scope; refusing fallback")
        try:
            contract = store.get(row.contract_hash)
            implementation = store.get(row.implementation_hash)
        except KeyError as exc:
            raise ScopedBindingError("binding references unknown semantic value") from exc
        if contract.kind != "contract":
            raise ScopedBindingError("expected target is not a contract")
        if implementation.kind != "implementation":
            raise ScopedBindingError("binding target is not an implementation")
        if not any(dep.relation == "implements"
                   and dep.target_hash == row.contract_hash
                   and dep.hash_relevant for dep in implementation.dependencies):
            raise ScopedBindingError("implementation does not declare exact contract")
        matches.append((layer, row))

    if not matches:
        raise ScopedBindingError(f"no binding found for key: {key}")
    winning_layer, winning_row = matches[-1]
    for lower, higher in zip(matches, matches[1:]):
        if (lower[0].scope, higher[0].scope) not in policy.allowed_overrides:
            raise ScopedBindingError(
                f"override from {lower[0].scope} to {higher[0].scope} is not allowed")

    payload = {
        "domain": "llmlang.resolved-binding.v1",
        "key": key,
        "contract_hash": expected_contract_hash,
        "implementation_hash": winning_row.implementation_hash,
        "winning_scope": winning_layer.scope,
        "winning_scope_id_hash": winning_layer.scope_id_hash,
        "policy_hash": policy.policy_hash,
        "consulted_layers": consulted,
        "resolver_version": "scoped-binding-resolver.v1",
    }
    root = digest(payload)
    return ResolvedBinding(root, key, expected_contract_hash,
                           winning_row.implementation_hash, winning_layer.scope,
                           winning_layer.scope_id_hash, policy.policy_hash,
                           tuple(consulted))
