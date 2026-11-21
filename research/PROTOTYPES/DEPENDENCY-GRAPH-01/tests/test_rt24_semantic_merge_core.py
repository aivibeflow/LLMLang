"""Three-way merge experiment over the closed RT-24 source inventory."""

from dataclasses import dataclass
from itertools import product
import subprocess
import unittest

from src.semantic_dependency_index import SemanticObjectError
from src.semantic_graph import canonical_bytes, make_snapshot
from tests import test_rt24_merge_tree_gate as tree_fixture
from tests.test_candidate_graph_audit import declaration
from tests.test_rt24_merge_tree_gate import (
    CALLEE, CALLER, CONTRACT, MANIFEST, GraphImportError, Inventory, InventoryError,
    commit, git, import_closed, manifest, read_inventory, row,
)


POLICY = "rt24-explicit-slot-v1"
EXPORT = "program/merged.json"


@dataclass(frozen=True)
class Conflict:
    kind: str
    slot: str
    base: str | None
    ours: str | None
    theirs: str | None


@dataclass(frozen=True)
class MergeResult:
    status: str
    inputs: tuple[tuple[str, str, str | None], ...]
    policy: str = POLICY
    conflicts: tuple[Conflict, ...] = ()
    reason: str = ""
    selections: tuple[tuple[str, str], ...] = ()
    export: bytes | None = None


def resolve_slot(slot, base, ours, theirs):
    if ours == base:
        return theirs, None
    if theirs == base:
        return ours, None
    if base is None:
        return None, Conflict("add-add", slot, base, ours, theirs)
    if ours == theirs:
        return ours, None
    kind = "delete-update" if None in (ours, theirs) else "update-update"
    return None, Conflict(kind, slot, base, ours, theirs)


def merge_inventories(base: Inventory, ours: Inventory, theirs: Inventory) -> MergeResult:
    """Produce a structural candidate under an explicitly scoped slot policy."""
    inputs = []
    states = []
    errors = []
    for role, inventory in zip(("base", "ours", "theirs"), (base, ours, theirs)):
        try:
            store, snapshot = import_closed(inventory)
        except (GraphImportError, SemanticObjectError) as exc:
            inputs.append((inventory.tree, inventory.blob_digest, None))
            errors.append(f"{role}: {exc}")
        else:
            inputs.append((inventory.tree, inventory.blob_digest, snapshot.root_hash))
            states.append((store, snapshot.mapping))
    pins = tuple(inputs)
    if errors:
        return MergeResult("invalid-input", pins, reason="; ".join(errors))

    old, left, right = (mapping for _, mapping in states)
    candidates = {}
    rows = {}
    conflicts = []
    for slot in sorted(old.keys() | left.keys() | right.keys()):
        address, conflict = resolve_slot(slot, old.get(slot), left.get(slot), right.get(slot))
        if conflict is not None:
            conflicts.append(conflict)
        elif address is not None:
            candidates[slot] = address
            # Obtain the exact selected value from an independently imported side.
            store = next(store for store, mapping in states if mapping.get(slot) == address)
            rows[slot] = store.get(address).payload
    if conflicts:
        return MergeResult("slot-conflict", pins, conflicts=tuple(conflicts))

    try:
        _, rebuilt = import_closed(Inventory("", "", rows))
    except (GraphImportError, SemanticObjectError) as exc:
        return MergeResult("graph-conflict", pins, reason=str(exc))
    if rebuilt != make_snapshot(candidates):
        return MergeResult("graph-conflict", pins, reason="reconstructed selections differ")

    export = canonical_bytes([row(slot, value) for slot, value in rows.items()]) + b"\n"
    return MergeResult("structural-candidate", pins, selections=rebuilt.selections, export=export)


class MergeCoreExperiment(unittest.TestCase):
    setUp = tree_fixture.MergeTreeGateExperiment.setUp

    def branches(self, ours, theirs):
        inventories = [read_inventory(self.repo, self.base)]
        for branch, files in (("ours", ours), ("theirs", theirs)):
            git(self.repo, "switch", "--quiet", "-c", branch, self.base)
            revision = commit(self.repo, files)
            inventories.append(read_inventory(self.repo, revision))
        return tuple(inventories)

    def test_all_single_slot_combinations(self):
        counts = {"resolved": 0, "add-add": 0, "update-update": 0, "delete-update": 0}
        for base, ours, theirs in product((None, "a", "b", "c"), repeat=3):
            with self.subTest(base=base, ours=ours, theirs=theirs):
                changed = {value for value in (ours, theirs) if value != base}
                address, conflict = resolve_slot("s", base, ours, theirs)
                reversed_address, reversed_conflict = resolve_slot("s", base, theirs, ours)
                self.assertEqual(address, reversed_address)
                if base is None and ours is not None and theirs is not None:
                    expected = "add-add"
                elif len(changed) < 2:
                    self.assertIsNone(conflict)
                    self.assertIsNone(reversed_conflict)
                    self.assertEqual(address, next(iter(changed), base))
                    counts["resolved"] += 1
                    continue
                else:
                    expected = "delete-update" if None in changed else "update-update"
                self.assertIsNone(address)
                self.assertEqual(conflict, Conflict(expected, "s", base, ours, theirs))
                self.assertEqual(reversed_conflict, Conflict(expected, "s", base, theirs, ours))
                counts[expected] += 1
        self.assertEqual(counts, {"resolved": 37, "add-add": 9, "update-update": 6, "delete-update": 12})

    def test_text_conflict_but_semantic_composition_and_round_trip(self):
        other = declaration("function", "function:independent")
        inventories = self.branches(
            {CALLEE: canonical_bytes([row("callee", self.new)]).decode() + "\n"},
            {CALLEE: canonical_bytes([row("callee", self.old), row("independent", other)]).decode() + "\n"},
        )
        # Both edits changed the same JSON file around the same declaration.
        git(self.repo, "switch", "--quiet", "ours")
        with self.assertRaises(subprocess.CalledProcessError):
            git(self.repo, "merge", "--no-commit", "theirs")
        self.assertEqual(git(self.repo, "diff", "--name-only", "--diff-filter=U").strip(),
                         CALLEE.encode())
        git(self.repo, "merge", "--abort")

        result = merge_inventories(*inventories)
        self.assertEqual(result.status, "structural-candidate")
        self.assertEqual(result, merge_inventories(*inventories))
        swapped = merge_inventories(inventories[0], inventories[2], inventories[1])
        self.assertEqual(result.export, swapped.export)
        self.assertEqual(swapped.inputs, (result.inputs[0], result.inputs[2], result.inputs[1]))
        git(self.repo, "switch", "--quiet", "-c", "export", self.base)
        revision = commit(self.repo, {
            MANIFEST: manifest(EXPORT), CALLEE: None, CALLER: None, CONTRACT: None,
            EXPORT: result.export.decode("utf-8"),
        })
        _, rebuilt = import_closed(read_inventory(self.repo, revision))
        self.assertEqual(rebuilt.selections, result.selections)
        self.assertEqual(set(rebuilt.mapping), {"callee", "contract", "independent"})
        replay = read_inventory(self.repo, revision)
        self.assertEqual(merge_inventories(replay, replay, replay).export, result.export)

    def test_disjoint_slots_can_produce_a_graph_conflict(self):
        inventories = self.branches(
            {CALLEE: [row("callee", self.new)]},
            {CALLER: [row("caller", self.caller)]},
        )
        result = merge_inventories(*inventories)
        self.assertEqual(result.status, "graph-conflict")
        self.assertIn(self.old_hash, result.reason)
        self.assertIsNone(result.export)
        self.assertEqual(result.selections, ())

    def test_preserving_old_declaration_keeps_exact_caller_pin(self):
        inventories = self.branches(
            {CALLEE: [row("callee", self.new), row("retained", self.old)]},
            {CALLER: [row("caller", self.caller)]},
        )
        result = merge_inventories(*inventories)
        self.assertEqual(result.status, "structural-candidate")
        selected = dict(result.selections)
        self.assertEqual(selected["retained"], self.old_hash)
        self.assertEqual(selected["caller"], import_closed(inventories[2])[1].mapping["caller"])
        self.assertNotEqual(selected["callee"], self.old_hash)

    def test_delete_update_reports_exact_input_versions(self):
        inventories = self.branches({CALLEE: []}, {CALLEE: [row("callee", self.new)]})
        result = merge_inventories(*inventories)
        target = import_closed(inventories[2])[1].mapping["callee"]
        self.assertEqual(result.status, "slot-conflict")
        self.assertEqual(result.conflicts, (Conflict("delete-update", "callee", self.old_hash,
                                                     None, target),))
        self.assertIsNone(result.export)

    def test_invalid_graph_or_missing_source_is_blocked_before_composition(self):
        inventories = self.branches(
            {CALLEE: [], CALLER: [row("caller", self.caller)]},
            {CALLER: [row("caller", self.caller)]},
        )
        result = merge_inventories(*inventories)
        self.assertEqual(result.status, "invalid-input")
        self.assertIsNone(result.inputs[1][2])
        self.assertIsNone(result.export)

        revision = commit(self.repo, {MANIFEST: manifest(CONTRACT, CALLEE)})
        with self.assertRaisesRegex(InventoryError, "inventor"):
            read_inventory(self.repo, revision)
