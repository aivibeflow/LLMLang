"""Ordered typed diff of exact, closed semantic inventories."""
from dataclasses import asdict, dataclass

from .candidate_semantic_diff import SelectionChange, _declaration_edges
from .semantic_graph import ContentStore, digest
from .semantic_merge_core import MergeInput, validate_closed_input


@dataclass(frozen=True, order=True)
class Occurrence:
    slot: str
    value_hash: str


@dataclass(frozen=True)
class Lineage:
    kind: str
    baseline_pin: str
    candidate_pin: str
    origins: tuple[Occurrence, ...]
    successors: tuple[Occurrence, ...]
    evidence_id: str


@dataclass(frozen=True)
class EdgeValue:
    relation: str
    target_hash: str
    condition: str | None
    required_contract_hash: str | None


@dataclass(frozen=True)
class EdgeDelta:
    slot: str
    edge_kind: str
    edge_id: str
    operation: str
    before: EdgeValue | None
    after: EdgeValue | None


@dataclass(frozen=True)
class EntryDelta:
    entrypoint: str
    before: Occurrence | None
    after: Occurrence | None


@dataclass(frozen=True)
class Diff:
    baseline_pin: str
    candidate_pin: str
    difference_id: str | None
    selections: tuple[SelectionChange, ...] = ()
    edges: tuple[EdgeDelta, ...] = ()
    entrypoints: tuple[EntryDelta, ...] = ()
    removed_values: tuple[str, ...] = ()
    added_values: tuple[str, ...] = ()
    lineage: tuple[Lineage, ...] = ()
    errors: tuple[str, ...] = ()


def _validate_lineage(rows, before, after):
    errors = []
    shape = {"rename": (1, 1), "split": (1, None), "merge": (None, 1)}
    baseline = before.snapshot.mapping
    candidate = after.snapshot.mapping
    for row in rows:
        if row.kind not in shape or not row.evidence_id:
            errors.append("lineage kind and evidence identity are required")
            continue
        if (row.baseline_pin, row.candidate_pin) != (before.exact_pin, after.exact_pin):
            errors.append(f"{row.evidence_id}: lineage is attached to different inputs")
            continue
        if any(mapping.get(endpoint.slot) != endpoint.value_hash
               for endpoints, mapping in ((row.origins, baseline), (row.successors, candidate))
               for endpoint in endpoints):
            errors.append(f"{row.evidence_id}: lineage endpoint is absent or stale")
        cardinality = shape[row.kind]
        if any(len(set(points)) != len(points) or (len(points) < 2 if size is None else len(points) != size)
               for points, size in zip((row.origins, row.successors), cardinality)):
            errors.append(f"{row.evidence_id}: lineage cardinality does not match the kind")
        if (row.kind == "rename" and len(row.origins) == len(row.successors) == 1
                and row.origins[0].slot == row.successors[0].slot):
            errors.append(f"{row.evidence_id}: rename retains the same slot")
    return tuple(sorted(set(errors)))


def _edge_values(store, address):
    if address is None:
        return {}
    return {selector: EdgeValue(*fields) for selector, fields in _declaration_edges(store, address).items()}


def _declaration_identity(store, address):
    value = store.get(address)
    return value.kind, value.payload["declaration_id"]


def _edge_changes(store, slot, old, new):
    before = _edge_values(store, old)
    after = _edge_values(store, new)
    if old is not None and new is not None and _declaration_identity(store, old) != _declaration_identity(store, new):
        for (kind, identity), value in sorted(before.items()):
            yield EdgeDelta(slot, kind, identity, "remove", value, None)
        for (kind, identity), value in sorted(after.items()):
            yield EdgeDelta(slot, kind, identity, "add", None, value)
        return
    for key in sorted(before.keys() | after.keys()):
        previous, current = before.get(key), after.get(key)
        if previous == current:
            continue
        if previous is None:
            operation = "add"
        elif current is None:
            operation = "remove"
        elif previous.target_hash != current.target_hash:
            operation = "retarget"
        else:
            operation = "modify"
        yield EdgeDelta(slot, *key, operation, previous, current)


def _entrypoints(inventory):
    selections = inventory.snapshot.mapping
    return {name: Occurrence(slot, selections[slot]) for name, slot in inventory.entrypoints}


def semantic_diff(store: ContentStore, before: MergeInput, after: MergeInput,
                  lineage: tuple[Lineage, ...] = ()) -> Diff:
    """Compare ordered selections and explicit lineage without inferring continuity."""
    pins = (before.exact_pin, after.exact_pin)
    input_conflicts = (*validate_closed_input(store, before, "baseline"),
                       *validate_closed_input(store, after, "candidate"))
    if input_conflicts:
        errors = tuple(f"{conflict.subject}/{conflict.kind}: {', '.join(conflict.details)}"
                       for conflict in input_conflicts)
        return Diff(*pins, None, errors=errors)
    errors = _validate_lineage(lineage, before, after)
    if errors:
        return Diff(*pins, None, errors=errors)

    old, new = before.snapshot.mapping, after.snapshot.mapping
    selections = []
    edges = []
    for slot in sorted(old.keys() | new.keys()):
        previous, current = old.get(slot), new.get(slot)
        if previous == current:
            continue
        operation = "add" if previous is None else "remove" if current is None else "replace"
        selections.append(SelectionChange(slot, operation, previous, current))
        edges.extend(_edge_changes(store, slot, previous, current))
    old_roots, new_roots = _entrypoints(before), _entrypoints(after)
    entrypoints = tuple(EntryDelta(name, old_roots.get(name), new_roots.get(name))
                        for name in sorted(old_roots.keys() | new_roots.keys())
                        if old_roots.get(name) != new_roots.get(name))
    ordered_lineage = tuple(sorted({
        Lineage(row.kind, row.baseline_pin, row.candidate_pin, tuple(sorted(row.origins)),
                tuple(sorted(row.successors)), row.evidence_id)
        for row in lineage
    }, key=lambda row: (row.kind, row.origins, row.successors, row.evidence_id)))
    removed = tuple(sorted(set(old.values()) - set(new.values())))
    added = tuple(sorted(set(new.values()) - set(old.values())))
    identity = digest({
        "domain": "llmlang.semantic-diff/1", "pins": pins,
        "selections": [asdict(row) for row in selections], "edges": [asdict(row) for row in edges],
        "entrypoints": [asdict(row) for row in entrypoints], "removed": removed, "added": added,
        "lineage": [asdict(row) for row in ordered_lineage],
    })
    return Diff(*pins, identity, tuple(selections), tuple(edges), entrypoints, removed, added, ordered_lineage)
