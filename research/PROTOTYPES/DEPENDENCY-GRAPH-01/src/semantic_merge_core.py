"""Pure three-way merge boundary for a closed, explicit declaration inventory."""
from dataclasses import dataclass
from typing import Mapping

from .candidate_graph_audit import audit_candidate_snapshot_graph
from .semantic_graph import ContentStore, Snapshot, digest, make_snapshot, merge_snapshots

CLOSED_POLICY = "closed-explicit-single-base/1"


def _input_digest(snapshot, entries, policy):
    return digest({"domain": "llmlang.closed-merge-input/1", "snapshot": snapshot.root_hash,
                   "entrypoints": entries, "policy": policy})


@dataclass(frozen=True)
class MergeInput:
    snapshot: Snapshot
    entrypoints: tuple[tuple[str, str], ...]
    policy: str
    exact_pin: str


def pin_merge_input(snapshot: Snapshot, entrypoints: Mapping[str, str],
                    policy: str = CLOSED_POLICY) -> MergeInput:
    entries = tuple(sorted(entrypoints.items()))
    return MergeInput(snapshot, entries, policy, _input_digest(snapshot, entries, policy))


@dataclass(frozen=True)
class MergeConflict:
    kind: str
    subject: str
    baseline: str | None = None
    ours: str | None = None
    theirs: str | None = None
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class MergeResult:
    input_pins: tuple[str, str, str]
    candidate: MergeInput | None = None
    conflicts: tuple[MergeConflict, ...] = ()


def _references_outside_inventory(store, snapshot):
    audit = audit_candidate_snapshot_graph(store, snapshot)
    outside = set(audit.reachable_hashes) - set(snapshot.mapping.values())
    return (*audit.errors, *(f"unselected dependency {value}" for value in sorted(outside)))


def _input_conflicts(store, entry, role):
    if entry.policy != CLOSED_POLICY:
        return (MergeConflict("unsupported-context", role, details=(entry.policy,)),)
    try:
        entries = dict(entry.entrypoints)
        if any(not isinstance(name, str) or not name or not isinstance(slot, str) or not slot
               for name, slot in entries.items()):
            return (MergeConflict("root", role, details=("malformed entrypoint mapping",)),)
        canonical = pin_merge_input(entry.snapshot, entries, entry.policy)
        selected = entry.snapshot.mapping
        semantic = make_snapshot(selected, entry.snapshot.parent_roots)
    except (TypeError, ValueError):
        return (MergeConflict("root", role, details=("malformed input inventory",)),)
    if entry != canonical or entry.snapshot != semantic:
        return (MergeConflict("root", role, details=("input does not match its exact pin",)),)
    invalid = sorted(name for name, slot in entries.items() if slot not in selected)
    if invalid:
        return (MergeConflict("root", role, details=tuple(invalid)),)
    dependencies = _references_outside_inventory(store, semantic)
    return (MergeConflict("dependency", role, details=dependencies),) if dependencies else ()


def _call_targets(store, content_hash):
    payload = store.get(content_hash).payload
    return {(site["call_site_id"], target["target_id"]): (
                target["target_hash"], target["required_contract_hash"], target["condition"],
            )
            for site in payload["call_sites"] for target in site["targets"]}


def _selection_conflicts(store, baseline, ours, theirs, changed):
    b, l, r = baseline.mapping, ours.mapping, theirs.mapping
    ambiguous_additions = (l.keys() & r.keys()) - b.keys()
    for slot in sorted(ambiguous_additions | changed.keys()):
        original, left, right = b.get(slot), l.get(slot), r.get(slot)
        details = ()
        if slot in ambiguous_additions:
            kind = "identity-lineage"
        elif left is None or right is None:
            kind = "delete-update"
        else:
            before = _call_targets(store, original)
            after_left = _call_targets(store, left)
            after_right = _call_targets(store, right)
            details = tuple(f"{site}/{target}" for site, target in sorted(before.keys())
                            if after_left.get((site, target)) != before[(site, target)]
                            and after_right.get((site, target)) != before[(site, target)]
                            and after_left.get((site, target)) != after_right.get((site, target)))
            kind = "retarget" if details else "update-update"
        yield MergeConflict(kind, slot, original, left, right, details)


def merge_closed(store: ContentStore, baseline: MergeInput, ours: MergeInput,
                 theirs: MergeInput) -> MergeResult:
    """Return a structural candidate or typed conflicts without changing the store."""
    inputs = (baseline, ours, theirs)
    pins = (baseline.exact_pin, ours.exact_pin, theirs.exact_pin)
    invalid = tuple(conflict for role, entry in zip(("base", "ours", "theirs"), inputs)
                    for conflict in _input_conflicts(store, entry, role))
    if invalid:
        return MergeResult(pins, conflicts=invalid)

    b, l, r = (entry.snapshot for entry in inputs)
    candidate, changed = merge_snapshots(b, l, r)
    conflicts = list(_selection_conflicts(store, b, l, r, changed))
    roots = [dict(entry.entrypoints) for entry in inputs]
    merged_roots, root_conflicts = merge_snapshots(*(make_snapshot(entries) for entries in roots))
    conflicts.extend(MergeConflict("root", name, *(entries.get(name) for entries in roots))
                     for name in sorted(root_conflicts))
    if conflicts:
        return MergeResult(pins, conflicts=tuple(conflicts))

    assert candidate is not None and merged_roots is not None
    entrypoints = merged_roots.mapping
    selections = candidate.mapping
    missing_roots = sorted((name, slot) for name, slot in entrypoints.items() if slot not in selections)
    if missing_roots:
        return MergeResult(pins, conflicts=tuple(
            MergeConflict("root", name, details=(f"entrypoint selects missing slot {slot}",))
            for name, slot in missing_roots
        ))
    missing_dependencies = _references_outside_inventory(store, candidate)
    if missing_dependencies:
        return MergeResult(pins, conflicts=(
            MergeConflict("dependency", "candidate", details=missing_dependencies),
        ))
    return MergeResult(pins, pin_merge_input(candidate, entrypoints))
