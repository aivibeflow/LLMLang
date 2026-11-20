"""Experimental RT-05 continuity rules over two exact selection states."""
from __future__ import annotations

from dataclasses import astuple, dataclass
from typing import Literal

from .semantic_graph import ContentStore, digest


@dataclass(frozen=True, order=True)
class Slot:
    scope: str
    key: str


@dataclass(frozen=True)
class Binding:
    slot: Slot
    value_hash: str
    context_hash: str
    alias: str
    entity_id: str | None = None

    def occurrence_hash(self) -> str:
        return digest({
            "domain": "llmlang.rt05-experimental-occurrence.v1",
            "value": self.value_hash,
            "context": self.context_hash,
            "slot": astuple(self.slot),
        })


@dataclass(frozen=True)
class State:
    bindings: tuple[Binding, ...]

    def __post_init__(self) -> None:
        slots = {binding.slot for binding in self.bindings}
        if len(slots) != len(self.bindings):
            raise ValueError("duplicate scoped slot")
        if any(not slot.scope or not slot.key for slot in slots):
            raise ValueError("a slot needs a scope and a local key")

    @property
    def revision(self) -> str:
        """Pin the whole fixture state, including aliases, for lineage records."""
        return digest({
            "domain": "llmlang.rt05-experimental-state.v1",
            "bindings": [astuple(binding) for binding in sorted(self.bindings, key=lambda b: b.slot)],
        })


@dataclass(frozen=True)
class Relation:
    kind: Literal["continue", "split", "merge"]
    before: tuple[Slot, ...]
    after: tuple[Slot, ...]


@dataclass(frozen=True)
class Lineage:
    base_revision: str
    candidate_revision: str
    relations: tuple[Relation, ...]


@dataclass(frozen=True)
class Comparison:
    relations: tuple[Relation, ...]
    unmatched_before: tuple[Slot, ...]
    unmatched_after: tuple[Slot, ...]


def _match_keys(
    bindings: tuple[Binding, ...],
    policy: str,
) -> dict[str | Slot, Slot]:
    if policy == "lineage":
        return {}
    if policy == "scoped-slot":
        return {binding.slot: binding.slot for binding in bindings}
    result: dict[str | Slot, Slot] = {}
    for binding in bindings:
        key = binding.entity_id
        if not key or key in result:
            raise ValueError("stable-id policy requires a unique entity ID per binding")
        result[key] = binding.slot
    return result


def compare(
    store: ContentStore,
    base: State,
    candidate: State,
    policy: Literal["stable-id", "lineage", "scoped-slot"],
    *,
    lineage: Lineage | None = None,
) -> Comparison:
    """Compare managed occurrences without inferring lineage from equal values."""
    if policy not in ("stable-id", "lineage", "scoped-slot"):
        raise ValueError("unknown continuation policy")
    for binding in base.bindings + candidate.bindings:
        if binding.value_hash not in store or binding.context_hash not in store:
            raise ValueError("binding references an unknown value or context")
    left_keys = _match_keys(base.bindings, policy)
    right_keys = _match_keys(candidate.bindings, policy)
    before_ids = {slot: key for key, slot in left_keys.items()}
    after_ids = {slot: key for key, slot in right_keys.items()}
    left = {binding.slot for binding in base.bindings}
    right = {binding.slot for binding in candidate.bindings}
    relations: list[Relation] = []

    def add(relation: Relation) -> None:
        before, after = set(relation.before), set(relation.after)
        sizes = (len(before), len(after))
        valid = (
            (relation.kind == "continue" and sizes == (1, 1))
            or (relation.kind == "split" and sizes[0] == 1 and sizes[1] >= 2)
            or (relation.kind == "merge" and sizes[0] >= 2 and sizes[1] == 1)
        )
        if not valid or len(before) != len(relation.before) or len(after) != len(relation.after):
            raise ValueError("invalid lineage cardinality or duplicate endpoint")
        if not before <= left or not after <= right:
            raise ValueError("lineage endpoint is absent or already assigned")
        if relation.kind == "continue" and policy == "stable-id":
            if before_ids[relation.before[0]] != after_ids[relation.after[0]]:
                raise ValueError("continuation cannot change a stable entity ID")
        left.difference_update(before)
        right.difference_update(after)
        relations.append(Relation(relation.kind, tuple(sorted(before)), tuple(sorted(after))))

    if lineage is not None:
        if (lineage.base_revision, lineage.candidate_revision) != (base.revision, candidate.revision):
            raise ValueError("lineage belongs to another revision pair")
        for relation in lineage.relations:
            add(relation)

    for key in left_keys.keys() & right_keys.keys():
        before, after = left_keys[key], right_keys[key]
        # An explicit split/merge can consume the endpoints of an implicit match.
        if before in left and after in right:
            add(Relation("continue", (before,), (after,)))

    return Comparison(
        tuple(sorted(relations, key=lambda relation: (relation.before, relation.after, relation.kind))),
        tuple(sorted(left)),
        tuple(sorted(right)),
    )
