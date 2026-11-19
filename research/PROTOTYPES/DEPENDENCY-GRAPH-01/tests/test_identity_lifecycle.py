from dataclasses import replace
import unittest

from src.identity_lifecycle import Binding, Comparison, Lineage, Relation, Slot, State, compare
from src.semantic_graph import ContentStore, make_snapshot, merge_snapshots


class IdentityLifecycleExperiment(unittest.TestCase):
    def setUp(self):
        self.store = ContentStore()
        self.original = self.store.put("function", {"value": 2})
        self.edited = self.store.put("function", {"value": 3})
        self.context = self.store.put("context", {"target": "test"})
        self.slot = Slot("module-a", "slot-1")
        self.binding = Binding(self.slot, self.original, self.context, "display", "entity-1")
        self.base = State((self.binding,))

    def test_display_alias_and_external_name_have_different_identity_effects(self):
        renamed = replace(self.binding, alias="new-display")
        candidate = State((renamed,))
        self.assertEqual(renamed.value_hash, self.binding.value_hash)
        self.assertEqual(renamed.occurrence_hash(), self.binding.occurrence_hash())
        self.assertNotEqual(candidate.revision, self.base.revision)
        for name in ("publicA", "publicB"):
            value_hash = self.store.put("operation", {"external_name": name})
            self.assertEqual(self.store.get(value_hash).payload["external_name"], name)
        self.assertNotEqual(
            self.store.put("operation", {"external_name": "publicA"}),
            self.store.put("operation", {"external_name": "publicB"}),
        )

    def test_equal_values_support_independent_edits_only_with_distinct_selectors(self):
        copy_slot = Slot("module-a", "slot-2")
        copy = replace(self.binding, slot=copy_slot, entity_id="entity-2")
        self.assertEqual(copy.value_hash, self.binding.value_hash)
        self.assertNotEqual(copy.occurrence_hash(), self.binding.occurrence_hash())
        base = State((self.binding, copy))
        candidate = State((replace(copy, value_hash=self.edited), self.binding))
        continues = (Relation("continue", (self.slot,), (self.slot,)),
                     Relation("continue", (copy_slot,), (copy_slot,)))
        for policy in ("stable-id", "scoped-slot"):
            self.assertEqual(compare(self.store, base, candidate, policy), Comparison(continues, (), ()))
        unmatched = (self.slot, copy_slot)
        self.assertEqual(compare(self.store, base, candidate, "lineage"), Comparison((), unmatched, unmatched))
        lineage = Lineage(base.revision, candidate.revision, continues)
        self.assertEqual(compare(self.store, base, candidate, "lineage", lineage=lineage),
                         Comparison(continues, (), ()))

    def test_cross_scope_move_requires_continuity_evidence_in_two_models(self):
        new_slot = Slot("module-b", self.slot.key)
        moved = replace(self.binding, slot=new_slot)
        candidate = State((moved,))
        self.assertNotEqual(moved.occurrence_hash(), self.binding.occurrence_hash())
        continuation = Relation("continue", (self.slot,), (new_slot,))
        matched = Comparison((continuation,), (), ())
        self.assertEqual(compare(self.store, self.base, candidate, "stable-id"), matched)
        for policy in ("lineage", "scoped-slot"):
            self.assertEqual(compare(self.store, self.base, candidate, policy),
                             Comparison((), (self.slot,), (new_slot,)))
            evidence = Lineage(self.base.revision, candidate.revision, (continuation,))
            self.assertEqual(compare(self.store, self.base, candidate, policy, lineage=evidence), matched)

    def test_context_edit_changes_occurrence_address_without_changing_the_managed_slot(self):
        context = self.store.put("context", {"target": "different"})
        changed = replace(self.binding, context_hash=context)
        candidate = State((changed,))
        self.assertEqual(changed.value_hash, self.binding.value_hash)
        self.assertNotEqual(changed.occurrence_hash(), self.binding.occurrence_hash())
        relation = Relation("continue", (self.slot,), (self.slot,))
        self.assertEqual(compare(self.store, self.base, candidate, "scoped-slot"),
                         Comparison((relation,), (), ()))

    def test_explicit_split_and_merge_do_not_guess_a_single_successor(self):
        first = self.binding
        second = replace(first, slot=Slot("module-a", "slot-2"), entity_id="entity-2", value_hash=self.edited)
        candidate = State((second, first))
        for before, after, relation in (
            (self.base, candidate, Relation("split", (first.slot,), (first.slot, second.slot))),
            (candidate, self.base, Relation("merge", (first.slot, second.slot), (first.slot,))),
        ):
            evidence = Lineage(before.revision, after.revision, (relation,))
            for policy in ("stable-id", "lineage", "scoped-slot"):
                self.assertEqual(compare(self.store, before, after, policy, lineage=evidence),
                                 Comparison((relation,), (), ()))

    def test_deletion_and_exact_recreation_expose_the_cost_of_slot_reuse(self):
        new_binding = replace(self.binding, entity_id="new-entity")
        recreated = State((new_binding,))
        self.assertEqual(new_binding.occurrence_hash(), self.binding.occurrence_hash())
        self.assertEqual(compare(self.store, self.base, recreated, "stable-id"),
                         Comparison((), (self.slot,), (self.slot,)))
        self.assertEqual(compare(self.store, self.base, recreated, "lineage"),
                         Comparison((), (self.slot,), (self.slot,)))
        # The two endpoint states alone cannot tell scoped-slot matching about the deletion.
        relation = Relation("continue", (self.slot,), (self.slot,))
        self.assertEqual(compare(self.store, self.base, recreated, "scoped-slot"),
                         Comparison((relation,), (), ()))
        fresh_slot = Slot(self.slot.scope, "slot-epoch-2")
        fresh = State((replace(new_binding, slot=fresh_slot),))
        self.assertEqual(compare(self.store, self.base, fresh, "scoped-slot"),
                         Comparison((), (self.slot,), (fresh_slot,)))
        # Without a lifetime token or history, the same endpoint is consistent
        # with both survival and deletion followed by recreation.
        content_only = State((replace(self.binding, entity_id=None),))
        self.assertEqual(
            content_only.revision,
            State((replace(new_binding, entity_id=None),)).revision,
        )

    def test_ordinal_call_site_keys_misidentify_two_equal_reordered_sites(self):
        call = self.store.put("call-site", {"target": self.original})
        context = self.store.put("context", {"caller": "current"})
        first = Binding(Slot("caller", "ordinal-1"), call, context, "first", "site-1")
        second = Binding(Slot("caller", "ordinal-2"), call, context, "second", "site-2")
        base = State((first, second))
        swapped = State((replace(first, slot=second.slot), replace(second, slot=first.slot)))
        actual_moves = (
            Relation("continue", (first.slot,), (second.slot,)),
            Relation("continue", (second.slot,), (first.slot,)),
        )
        self.assertEqual(compare(self.store, base, swapped, "stable-id").relations, actual_moves)
        by_ordinal = compare(self.store, base, swapped, "scoped-slot")
        self.assertEqual(by_ordinal.relations, (
            Relation("continue", (first.slot,), (first.slot,)),
            Relation("continue", (second.slot,), (second.slot,)),
        ))
        lineage = Lineage(base.revision, swapped.revision, actual_moves)
        self.assertEqual(compare(self.store, base, swapped, "scoped-slot", lineage=lineage).relations,
                         actual_moves)

    def test_stale_conflicting_and_invalid_lineage_fail_closed(self):
        candidate = State((replace(self.binding, value_hash=self.edited),))
        valid = Relation("continue", (self.slot,), (self.slot,))
        evidence = Lineage(self.base.revision, candidate.revision, (valid,))
        changed_again = State((replace(candidate.bindings[0], alias="changed"),))
        with self.assertRaisesRegex(ValueError, "another revision pair"):
            compare(self.store, self.base, changed_again, "lineage", lineage=evidence)
        with self.assertRaisesRegex(ValueError, "already assigned"):
            compare(self.store, self.base, candidate, "lineage",
                    lineage=replace(evidence, relations=(valid, valid)))
        invalid = Relation("split", (self.slot,), (self.slot, self.slot))
        with self.assertRaisesRegex(ValueError, "cardinality or duplicate endpoint"):
            compare(self.store, self.base, candidate, "lineage",
                    lineage=replace(evidence, relations=(invalid,)))
        with self.assertRaisesRegex(ValueError, "duplicate scoped slot"):
            State((self.binding, self.binding))
        duplicate_id = replace(self.binding, slot=Slot("module-b", "other"))
        with self.assertRaisesRegex(ValueError, "unique entity ID"):
            compare(self.store, self.base, State((self.binding, duplicate_id)), "stable-id")
        replaced = State((replace(self.binding, entity_id="new-entity"),))
        with self.assertRaisesRegex(ValueError, "cannot change a stable entity ID"):
            compare(self.store, self.base, replaced, "stable-id",
                    lineage=replace(evidence, candidate_revision=replaced.revision))

    def test_existing_selection_merge_distinguishes_disjoint_and_competing_edits(self):
        base = make_snapshot({"a": self.original, "b": self.original})
        left = make_snapshot({"a": self.edited, "b": self.original}, (base.root_hash,))
        right = make_snapshot({"a": self.original, "b": self.edited}, (base.root_hash,))
        merged, conflicts = merge_snapshots(base, left, right)
        self.assertEqual(conflicts, {})
        self.assertEqual(merged.mapping, {"a": self.edited, "b": self.edited})
        another = self.store.put("function", {"value": 4})
        competing = make_snapshot({"a": another, "b": self.original}, (base.root_hash,))
        self.assertEqual(merge_snapshots(base, left, competing),
                         (None, {"a": (self.edited, another)}))


if __name__ == "__main__":
    unittest.main()
