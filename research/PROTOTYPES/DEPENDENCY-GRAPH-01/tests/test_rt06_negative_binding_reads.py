"""Differential study of dependency keys for exact scoped binding lookups."""

from collections import Counter
from itertools import combinations, product
import unittest

from src.scoped_binding import (
    BindingLayer, BindingPolicy, ScopedBinding, ScopedBindingError, resolve_scoped_binding,
)
from src.semantic_graph import ContentStore, Dependency, digest


SCOPES = ("project", "tenant", "request")
KEY = "render"


def projected_key(layers, policy, contract, key=KEY):
    """Project the closed fixture's validated snapshot layers onto one lookup key."""
    by_scope = {layer.scope: layer for layer in layers}
    reads = []
    for scope in policy.precedence:
        layer = by_scope.get(scope)
        if layer is None:
            reads.append((scope, "layer-absent"))
            continue
        row = next((row for row in layer.bindings if row.key == key), None)
        if row is None:
            reads.append((scope, layer.scope_id_hash, "key-absent"))
        else:
            reads.append((scope, layer.scope_id_hash, "match", row.contract_hash,
                          row.implementation_hash))
    return digest(("rt06-scoped-key-projection/1", key, contract, policy.policy_hash, reads))


def whole_view_key(layers, policy, contract):
    return digest(("whole", KEY, contract, policy.policy_hash,
                   [(layer.scope, layer.scope_id_hash, layer.snapshot_root) for layer in layers]))


def observe(store, layers, policy, contract):
    try:
        resolved = resolve_scoped_binding(store, KEY, contract, layers, policy)
    except ScopedBindingError as exc:
        return ("rejected", str(exc))
    return ("selected", resolved.winning_scope, resolved.winning_scope_id_hash,
            resolved.implementation_hash)


def positive_only_key(layers, policy, contract):
    """Control that records the first present row in priority order and omits the rest."""
    for layer in reversed(layers):
        for row in layer.bindings:
            if row.key == KEY:
                return (policy.policy_hash, contract, layer.scope, layer.scope_id_hash,
                        row.contract_hash, row.implementation_hash)
    return (policy.policy_hash, contract, "no-binding")


class NegativeBindingReadsExperiment(unittest.TestCase):
    def setUp(self):
        self.store = ContentStore()
        self.required = self.store.put("contract", {"version": 1})
        self.wrong = self.store.put("contract", {"version": 2})
        self.a = self.store.put("implementation", {"name": "a"},
                                [Dependency("implements", self.required)])
        self.b = self.store.put("implementation", {"name": "b"},
                                [Dependency("implements", self.required)])
        self.c = self.store.put("implementation", {"name": "c"},
                                [Dependency("implements", self.wrong)])
        self.permissive = BindingPolicy.create()
        self.restricted = BindingPolicy.create(allowed_overrides=(("project", "tenant"),))

    def layer(self, scope, rows, scope_id=None):
        return BindingLayer(scope, digest(scope_id or scope),
                            digest([(row.key, row.contract_hash, row.implementation_hash)
                                    for row in rows]), tuple(rows))

    def view(self, statuses):
        rows = {
            "empty": (),
            "unrelated": (ScopedBinding("status", self.required, self.a),),
            "a": (ScopedBinding(KEY, self.required, self.a),),
            "b": (ScopedBinding(KEY, self.required, self.b),),
            "wrong": (ScopedBinding(KEY, self.wrong, self.c),),
        }
        return tuple(self.layer(scope, rows[status])
                     for scope, status in zip(SCOPES, statuses) if status != "missing")

    def test_complete_projection_matches_resolution_on_exhaustive_fixtures(self):
        statuses = ("missing", "empty", "unrelated", "a", "b", "wrong")
        views = list(product(statuses, repeat=3))
        totals = Counter()
        for policy in (self.permissive, self.restricted):
            rows = {}
            for choice in views:
                layers = self.view(choice)
                rows[choice] = (
                    observe(self.store, layers, policy, self.required),
                    projected_key(layers, policy, self.required),
                    whole_view_key(layers, policy, self.required),
                    positive_only_key(layers, policy, self.required),
                )
            for first, second in combinations(views, 2):
                if sum(lhs != rhs for lhs, rhs in zip(first, second)) != 1:
                    continue
                old, new = rows[first], rows[second]
                totals["transitions"] += 1
                totals["projection-reuses"] += old[1] == new[1]
                totals["whole-view-reuses"] += old[2] == new[2]
                totals["positive-only-false-reuses"] += old[3] == new[3] and old[0] != new[0]
                if old[1] == new[1]:
                    self.assertEqual(old[0], new[0], (first, second))
        self.assertEqual(totals, {
            "transitions": 3240, "projection-reuses": 216, "whole-view-reuses": 0,
            "positive-only-false-reuses": 516,
        })

    def test_new_higher_priority_binding_and_contract_conflict_are_visible(self):
        base = self.view(("a", "empty", "missing"))
        for updated in (self.view(("a", "b", "missing")),
                        self.view(("a", "wrong", "missing"))):
            with self.subTest(updated=updated):
                self.assertNotEqual(projected_key(base, self.permissive, self.required),
                                    projected_key(updated, self.permissive, self.required))
                self.assertNotEqual(observe(self.store, base, self.permissive, self.required),
                                    observe(self.store, updated, self.permissive, self.required))

    def test_lower_candidate_can_block_a_high_valid_provider(self):
        base = self.view(("missing", "empty", "a"))
        updated = self.view(("wrong", "empty", "a"))
        self.assertEqual(positive_only_key(base, self.permissive, self.required),
                         positive_only_key(updated, self.permissive, self.required))
        self.assertNotEqual(projected_key(base, self.permissive, self.required),
                            projected_key(updated, self.permissive, self.required))
        self.assertEqual(observe(self.store, base, self.permissive, self.required)[0], "selected")
        self.assertEqual(observe(self.store, updated, self.permissive, self.required)[0], "rejected")

    def test_scope_policy_and_contract_are_independent_inputs(self):
        view = self.view(("a", "missing", "b"))
        base = projected_key(view, self.permissive, self.required)
        self.assertNotEqual(base, projected_key(view, self.restricted, self.required))
        self.assertNotEqual(base, projected_key(view, self.permissive, self.wrong))
        reowned = (self.layer("project", view[0].bindings, "other-owner"), *view[1:])
        self.assertNotEqual(base, projected_key(reowned, self.permissive, self.required))

    def test_projection_requires_validated_whole_layers(self):
        original = self.view(("a", "unrelated", "missing"))
        unrelated, = original[1].bindings
        duplicate = (original[0], self.layer("tenant", (unrelated, unrelated)))
        self.assertEqual(projected_key(original, self.permissive, self.required),
                         projected_key(duplicate, self.permissive, self.required))
        self.assertEqual(observe(self.store, original, self.permissive, self.required)[0],
                         "selected")
        self.assertEqual(observe(self.store, duplicate, self.permissive, self.required),
                         ("rejected", "duplicate binding key in tenant layer"))
