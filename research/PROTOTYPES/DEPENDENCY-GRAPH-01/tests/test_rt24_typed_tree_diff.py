"""Extract exact semantic differences from two independently imported Git trees."""

from dataclasses import dataclass
import unittest

from src.semantic_dependency_index import publish_declaration, validate_declaration
from src.semantic_graph import digest
from tests import test_rt24_merge_tree_gate as fixtures


@dataclass(frozen=True)
class Edge:
    target: str
    condition: str | None
    required_contract: str | None
    target_kind: str


@dataclass(frozen=True)
class EdgeChange:
    slot: str
    edge_kind: str
    selector: tuple[str, ...]
    operation: str
    before: Edge | None
    after: Edge | None


@dataclass(frozen=True)
class TypedDiff:
    before: tuple[str, str, str]  # Git tree, inventory digest, semantic root
    after: tuple[str, str, str]
    selections: tuple[tuple[str, str, str | None, str | None], ...]
    content_changes: tuple[tuple[str, str, str], ...]
    edges: tuple[EdgeChange, ...]

    @property
    def semantic_identity(self):
        return digest(("rt24-semantic-diff/1", self.before[2], self.after[2]))

    @property
    def evidence_identity(self):
        return digest(("rt24-tree-diff/1", self.before, self.after, self.semantic_identity))


def declared_edges(declaration):
    references = {
        ("reference", ref["reference_id"], ref["relation"]):
            Edge(ref["target_hash"], ref["condition"], None, ref["target_kind"])
        for ref in declaration.get("references", ())
    }
    calls = {
        ("call", site["call_site_id"], call["target_id"]):
            Edge(call["target_hash"], call["condition"], call["required_contract_hash"], "callable")
        for site in declaration.get("call_sites", ()) for call in site["targets"]
    }
    return references | calls


def diff(before, after):
    """Report closed-inventory changes without inferring continuity across slots."""
    _, old_snap = fixtures.import_closed(before)
    _, new_snap = fixtures.import_closed(after)
    old, new = old_snap.mapping, new_snap.mapping
    selections, content_changes, edges = [], [], []
    for slot in sorted(old.keys() | new.keys()):
        was, now = old.get(slot), new.get(slot)
        if was == now:
            continue
        old_row = validate_declaration(before.declarations[slot]) if was is not None else None
        new_row = validate_declaration(after.declarations[slot]) if now is not None else None
        if old_row is None:
            change = "add"
        elif new_row is None:
            change = "remove"
        elif ((old_row["kind"], old_row["declaration_id"]) !=
              (new_row["kind"], new_row["declaration_id"])):
            change = "replace"
        else:
            change = "update"
        selections.append((slot, change, was, now))

        # Require exact declaration continuity within a slot when pairing edges.
        if change != "update":
            continue
        lhs = digest(old_row["content"])
        rhs = digest(new_row["content"])
        if lhs != rhs:
            content_changes.append((slot, lhs, rhs))
        old_edges, new_edges = declared_edges(old_row), declared_edges(new_row)
        for selector in sorted(old_edges.keys() | new_edges.keys()):
            left = old_edges.get(selector)
            right = new_edges.get(selector)
            if left == right:
                continue
            if left is None:
                operation = "add"
            elif right is None:
                operation = "remove"
            elif left.target != right.target:
                operation = "retarget"
            else:
                operation = "modify"
            edges.append(EdgeChange(slot, selector[0], selector[1:], operation, left, right))
    return TypedDiff(
        (before.tree, before.blob_digest, old_snap.root_hash),
        (after.tree, after.blob_digest, new_snap.root_hash),
        tuple(selections), tuple(content_changes), tuple(edges),
    )


class SemanticTreeDiffExperiment(unittest.TestCase):
    setUp = fixtures.MergeTreeGateExperiment.setUp

    def test_physical_move_keeps_semantic_diff_and_changes_evidence(self):
        path = "program/moved.json"
        old = fixtures.read_inventory(self.repo, self.base)
        revision = fixtures.commit(self.repo, {
            fixtures.CALLEE: None, path: [fixtures.row("callee", self.old)],
            fixtures.MANIFEST: fixtures.manifest(fixtures.CALLER, path, fixtures.CONTRACT),
        })
        new = fixtures.read_inventory(self.repo, revision)
        moved = diff(old, new)
        same = diff(old, old)
        self.assertEqual(moved.selections, ())
        self.assertEqual(moved.content_changes, ())
        self.assertEqual(moved.edges, ())
        self.assertEqual(moved.semantic_identity, same.semantic_identity)
        self.assertNotEqual(moved.evidence_identity, same.evidence_identity)

    def test_exact_retarget_and_condition_changes_keep_target_selectors(self):
        store, _ = fixtures.import_closed(fixtures.read_inventory(self.repo, self.base))
        new_id = publish_declaration(store, self.new)
        first = self.caller["call_sites"][0]["targets"][0]
        another = {**first, "target_id": "alternative", "condition": "alternate"}
        old_caller = {**self.caller, "call_sites": [
            {"call_site_id": "invoke", "targets": [another, first]},
        ]}
        next_caller = {**self.caller, "call_sites": [
            {"call_site_id": "invoke", "targets": [
                {**first, "target_hash": new_id}, {**another, "condition": "rechecked"},
            ]},
        ]}
        old = fixtures.commit(self.repo, {
            fixtures.CALLER: [fixtures.row("caller", old_caller)],
        })
        new = fixtures.commit(self.repo, {
            fixtures.CALLER: [fixtures.row("caller", next_caller)],
            fixtures.CALLEE: [fixtures.row("callee", self.new), fixtures.row("old", self.old)],
        })
        a, b = (fixtures.read_inventory(self.repo, revision) for revision in (old, new))
        forward = diff(a, b)
        self.assertEqual(forward, diff(a, b))
        self.assertEqual(len(forward.content_changes), 1)
        self.assertEqual(forward.content_changes[0][0], "callee")
        self.assertEqual([(edge.selector, edge.operation) for edge in forward.edges], [
            (("invoke", "alternative"), "modify"), (("invoke", "direct"), "retarget"),
        ])
        retarget = forward.edges[-1]
        self.assertEqual((retarget.before.target, retarget.after.target), (self.old_hash, new_id))
        self.assertEqual(retarget.after.required_contract, self.contract_hash)
        self.assertEqual(diff(b, a).edges[-1].after, retarget.before)
        self.assertNotEqual(diff(b, a).semantic_identity, forward.semantic_identity)

    def test_same_payload_in_a_new_slot_remains_add_remove(self):
        new = fixtures.commit(self.repo, {
            fixtures.CALLEE: [fixtures.row("callee2", self.old)],
        })
        a, b = (fixtures.read_inventory(self.repo, revision) for revision in (self.base, new))
        self.assertEqual(diff(a, b).selections, (
            ("callee", "remove", self.old_hash, None), ("callee2", "add", None, self.old_hash),
        ))

    def test_incomplete_source_never_yields_an_empty_diff(self):
        new = fixtures.commit(self.repo, {
            fixtures.CALLEE: [fixtures.row("callee", self.new)],
            fixtures.CALLER: [fixtures.row("caller", self.caller)],
        })
        a, b = (fixtures.read_inventory(self.repo, revision) for revision in (self.base, new))
        with self.assertRaisesRegex(fixtures.GraphImportError, self.old_hash):
            diff(a, b)

    def test_replacement_does_not_claim_edge_continuity(self):
        installed = fixtures.commit(self.repo, {
            fixtures.CALLER: [fixtures.row("caller", self.caller)],
        })
        replacement = {**self.caller, "declaration_id": "function:replacement", "call_sites": []}
        changed = fixtures.commit(self.repo, {
            fixtures.CALLER: [fixtures.row("caller", replacement)],
        })
        old, new = (fixtures.read_inventory(self.repo, rev) for rev in (installed, changed))
        result = diff(old, new)
        self.assertEqual(result.selections[0][:2], ("caller", "replace"))
        self.assertEqual(result.edges, ())
