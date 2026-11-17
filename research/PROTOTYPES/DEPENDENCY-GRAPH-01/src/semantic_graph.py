"""Minimal content-addressed semantic dependency graph prototype.

This is an experiment, not a production storage engine or a language runtime.
Only explicit, hash-relevant dependencies participate in semantic value hashes.
Project snapshots, provenance, and lineage are separate records.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Iterable, Mapping


def canonical_bytes(value: Any) -> bytes:
    """Deterministic JSON encoding for the prototype's restricted data model."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


@dataclass(frozen=True, order=True)
class Dependency:
    relation: str
    target_hash: str
    role: str = ""
    hash_relevant: bool = True

    def record(self) -> dict[str, Any]:
        return {
            "relation": self.relation,
            "target_hash": self.target_hash,
            "role": self.role,
            "hash_relevant": self.hash_relevant,
        }


@dataclass(frozen=True)
class SemanticValue:
    value_hash: str
    kind: str
    payload_json: str
    dependencies: tuple[Dependency, ...]

    @property
    def payload(self) -> Any:
        # Return a fresh object so callers cannot mutate stored semantic state.
        return json.loads(self.payload_json)


class ContentStore:
    """In-memory immutable value store with hash-based deduplication."""

    def __init__(self) -> None:
        self._values: dict[str, SemanticValue] = {}

    def put(
        self,
        kind: str,
        payload: Any,
        dependencies: Iterable[Dependency] = (),
    ) -> str:
        supplied_deps = tuple(sorted(dependencies))
        for dep in supplied_deps:
            if dep.target_hash not in self._values:
                raise KeyError(f"unknown dependency: {dep.target_hash}")
        # Non-semantic relations are deliberately not stored on the value.
        # They belong in RelationStore, scoped to a project/change context.
        deps = tuple(d for d in supplied_deps if d.hash_relevant)
        payload_json = canonical_bytes(payload).decode("utf-8")
        normalized_payload = json.loads(payload_json)
        canonical = {
            "domain": "llmlang.semantic-value.v1",
            "kind": kind,
            "payload": normalized_payload,
            "dependencies": [d.record() for d in deps],
        }
        value_hash = digest(canonical)
        value = SemanticValue(value_hash, kind, payload_json, deps)
        existing = self._values.get(value_hash)
        if existing is not None and existing != value:
            raise RuntimeError("hash collision or canonicalization inconsistency")
        self._values[value_hash] = value
        return value_hash

    def get(self, value_hash: str) -> SemanticValue:
        return self._values[value_hash]

    def __contains__(self, value_hash: str) -> bool:
        return value_hash in self._values

    def __len__(self) -> int:
        return len(self._values)

    def hashes(self) -> set[str]:
        return set(self._values)

    def reverse_dependencies(self) -> dict[str, set[str]]:
        reverse: dict[str, set[str]] = {h: set() for h in self._values}
        for source_hash, value in self._values.items():
            for dep in value.dependencies:
                reverse.setdefault(dep.target_hash, set()).add(source_hash)
        return reverse

    def dependents(self, target_hash: str, transitive: bool = False) -> set[str]:
        reverse = self.reverse_dependencies()
        direct = set(reverse.get(target_hash, set()))
        if not transitive:
            return direct
        seen: set[str] = set()
        todo = list(direct)
        while todo:
            current = todo.pop()
            if current in seen:
                continue
            seen.add(current)
            todo.extend(reverse.get(current, set()) - seen)
        return seen

    def active_dependents(self, snapshot: "Snapshot", target_hash: str) -> set[str]:
        """Dependents selected by this snapshot, excluding historical values."""
        selected = set(snapshot.mapping.values())
        return {
            source_hash
            for source_hash in selected
            if any(dep.target_hash == target_hash for dep in self.get(source_hash).dependencies)
        }

    def closure_digest(self, root_hash: str) -> str:
        """Digest the reachable hash-relevant value closure in deterministic order."""
        seen: set[str] = set()
        todo = [root_hash]
        while todo:
            current = todo.pop()
            if current in seen:
                continue
            seen.add(current)
            value = self.get(current)
            todo.extend(d.target_hash for d in value.dependencies)
        return digest({"domain": "llmlang.closure.v1", "members": sorted(seen)})


class RelationStore:
    """Context-scoped non-semantic relations (provenance, lineage, traceability)."""

    def __init__(self) -> None:
        self._relations: set[tuple[str, str, str, str]] = set()

    def add(self, scope: str, source_hash: str, relation: str, target: str) -> None:
        self._relations.add((scope, source_hash, relation, target))

    def for_scope(self, scope: str) -> set[tuple[str, str, str, str]]:
        return {r for r in self._relations if r[0] == scope}


@dataclass(frozen=True)
class Snapshot:
    root_hash: str
    selections: tuple[tuple[str, str], ...]
    parent_roots: tuple[str, ...] = ()

    @property
    def mapping(self) -> dict[str, str]:
        return dict(self.selections)


def make_snapshot(
    selections: Mapping[str, str], parent_roots: Iterable[str] = ()
) -> Snapshot:
    ordered = tuple(sorted(selections.items()))
    parents = tuple(sorted(set(parent_roots)))
    root_hash = digest({
        "domain": "llmlang.project-snapshot.v1",
        "selections": ordered,
        "parents": parents,
    })
    return Snapshot(root_hash, ordered, parents)


def merge_snapshots(
    base: Snapshot, left: Snapshot, right: Snapshot
) -> tuple[Snapshot | None, dict[str, tuple[str, str]]]:
    """Three-way merge by logical selection key; report conflicting keys."""
    b, l, r = base.mapping, left.mapping, right.mapping
    merged = dict(b)
    conflicts: dict[str, tuple[str, str]] = {}
    for key in set(b) | set(l) | set(r):
        bv, lv, rv = b.get(key), l.get(key), r.get(key)
        left_changed = lv != bv
        right_changed = rv != bv
        if left_changed and right_changed and lv != rv:
            conflicts[key] = (str(lv), str(rv))
        elif left_changed:
            if lv is None:
                merged.pop(key, None)
            else:
                merged[key] = lv
        elif right_changed:
            if rv is None:
                merged.pop(key, None)
            else:
                merged[key] = rv
    if conflicts:
        return None, conflicts
    return make_snapshot(merged, (left.root_hash, right.root_hash)), {}


def verification_key(
    value_hash: str,
    closure_digest: str,
    verifier_id: str,
    config: Mapping[str, Any],
    assumptions: Iterable[str] = (),
) -> str:
    return digest({
        "domain": "llmlang.verification-key.v1",
        "value_hash": value_hash,
        "closure_digest": closure_digest,
        "verifier_id": verifier_id,
        "config": config,
        "assumptions": sorted(assumptions),
    })


def run_100_caller_experiment() -> dict[str, Any]:
    store = ContentStore()
    tax_h0 = store.put("function", {"name": "calculate_tax", "rule": "old"})
    old_callers = {
        f"caller_{i:03d}": store.put(
            "function",
            {"body": f"invoice_total_{i:03d}"},
            [Dependency("calls", tax_h0, "tax")],
        )
        for i in range(1, 101)
    }
    base = make_snapshot({"calculate_tax": tax_h0, **old_callers})

    tax_h1 = store.put("function", {"name": "calculate_tax", "rule": "new"})
    changed_callers = dict(old_callers)
    for i in (1, 2, 3):
        key = f"caller_{i:03d}"
        changed_callers[key] = store.put(
            "function",
            {"body": f"invoice_total_{i:03d}"},
            [Dependency("calls", tax_h1, "tax")],
        )
    candidate = make_snapshot(
        {"calculate_tax": tax_h1, **changed_callers}, (base.root_hash,)
    )

    changed = [k for k in old_callers if old_callers[k] != changed_callers[k]]
    unchanged = [k for k in old_callers if old_callers[k] == changed_callers[k]]
    return {
        "base_root": base.root_hash,
        "candidate_root": candidate.root_hash,
        "tax_h0": tax_h0,
        "tax_h1": tax_h1,
        "caller_count": len(old_callers),
        "changed_callers": changed,
        "unchanged_callers": len(unchanged),
        "old_tax_still_stored": tax_h0 in store,
        "new_tax_stored": tax_h1 in store,
        "distinct_semantic_values": len(store),
        "historical_dependents_of_old_tax": len(store.dependents(tax_h0)),
        "active_dependents_of_old_tax": len(store.active_dependents(candidate, tax_h0)),
        "active_dependents_of_new_tax": len(store.active_dependents(candidate, tax_h1)),
    }


if __name__ == "__main__":
    print(json.dumps(run_100_caller_experiment(), indent=2, sort_keys=True))
