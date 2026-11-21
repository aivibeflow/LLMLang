"""A narrow three-way merge law for exact call-target substitutions."""

from dataclasses import dataclass
import json
import unittest

from src.semantic_dependency_index import publish_declaration, validate_declaration
from src.semantic_graph import canonical_bytes
from tests import test_rt24_merge_tree_gate as tree
from tests.test_candidate_graph_audit import declaration
from tests.test_candidate_semantic_diff_cip_v2 import call_site
from tests.test_rt24_semantic_merge_core import resolve_slot


class CallMergeConflict(ValueError):
    pass


def targets(row):
    return {(site["call_site_id"], target["target_id"]): target
            for site in row["call_sites"] for target in site["targets"]}


def merge_call_targets(base, left, right):
    rows = [validate_declaration(row) for row in (base, left, right)]
    common = [{key: value for key, value in row.items() if key != "call_sites"} for row in rows]
    if common[0] != common[1] or common[0] != common[2]:
        raise CallMergeConflict("caller identity, content or references changed")

    old, ours, theirs = map(targets, rows)
    if old.keys() != ours.keys() or old.keys() != theirs.keys():
        raise CallMergeConflict("call selectors changed")
    merged = {}
    for selector, value in old.items():
        before = value["target_hash"]
        for row in (ours[selector], theirs[selector]):
            if {**row, "target_hash": before} != value:
                raise CallMergeConflict(f"call guard or contract changed at {selector}")
        left_target = ours[selector]["target_hash"]
        right_target = theirs[selector]["target_hash"]
        result, conflict = resolve_slot(str(selector), before, left_target, right_target)
        if conflict is not None:
            raise CallMergeConflict(f"competing retargets at {selector}")
        merged[selector] = {**value, "target_hash": result}

    return {**common[0], "call_sites": [
        {"call_site_id": site["call_site_id"], "targets": [
            merged[site["call_site_id"], row["target_id"]] for row in site["targets"]
        ]} for site in rows[0]["call_sites"]
    ]}


@dataclass(frozen=True)
class Candidate:
    pins: tuple[tuple[str, str, str], ...]
    selections: tuple[tuple[str, str], ...]
    export: bytes


def merge_closed(base, left, right, selected_caller):
    """Compose selected slots, allowing retargets only for the declared fixture caller."""
    inventories = (base, left, right)
    states = [tree.import_closed(item)[1] for item in inventories]
    roots = tuple((item.tree, item.blob_digest, state.root_hash)
                  for item, state in zip(inventories, states))
    maps = [state.mapping for state in states]
    rows = {}
    for slot in sorted(set().union(*maps)):
        addresses = tuple(mapping.get(slot) for mapping in maps)
        result, conflict = resolve_slot(slot, *addresses)
        if conflict is not None:
            if slot != selected_caller or None in addresses:
                raise CallMergeConflict(f"conflicting selection at {slot}")
            rows[slot] = merge_call_targets(*(item.declarations[slot] for item in inventories))
        elif result is not None:
            source = next(item for item, address in zip(inventories, addresses)
                          if address == result)
            rows[slot] = validate_declaration(source.declarations[slot])

    _, validated = tree.import_closed(tree.Inventory("", "", rows))
    export = canonical_bytes([tree.row(slot, value) for slot, value in rows.items()])
    return Candidate(roots, validated.selections, export)


class CallTargetMergeExperiment(unittest.TestCase):
    setUp = tree.MergeTreeGateExperiment.setUp

    def branches(self, left_form, right_form, *, upstream=False, retain=False, branch_pin=False):
        inventory = tree.read_inventory(self.repo, self.base)
        store, _ = tree.import_closed(inventory)
        self.left_hash = publish_declaration(store, self.new)
        alternate = {**self.old, "content": {"offset": 3}}
        self.right_hash = publish_declaration(store, alternate)
        caller = {**self.caller, "references": self.old["references"], "call_sites": [
            call_site("first", self.old_hash, self.contract_hash),
            call_site("second", self.old_hash, self.contract_hash),
        ]}
        original_hash = publish_declaration(store, caller)
        callers = [tree.row("caller", caller)]
        if retain:
            callers.append(tree.row("caller.old", caller))
        if upstream:
            callers.append(tree.row("upstream", declaration(
                "function", "function:upstream", call_sites=[
                    call_site("outer", original_hash, self.contract_hash),
                ],
            )))
        base = tree.commit(self.repo, {
            tree.CALLEE: [tree.row("old", self.old), tree.row("left", self.new), tree.row("right", alternate)],
            tree.CALLER: callers,
        })
        inventories = [tree.read_inventory(self.repo, base)]
        for branch, form in (("left", left_form), ("right", right_form)):
            tree.git(self.repo, "switch", "--quiet", "-c", branch, base)
            edited = form(caller)
            branch_rows = [tree.row("caller", edited), *callers[1:]]
            if branch == "left" and branch_pin:
                exact = publish_declaration(store, edited)
                branch_rows.append(tree.row("upstream", declaration(
                    "function", "function:branch-user", call_sites=[
                        call_site("outer", exact, self.contract_hash),
                    ],
                )))
            changed = tree.commit(self.repo, {tree.CALLER: branch_rows})
            inventories.append(tree.read_inventory(self.repo, changed))
        return inventories

    def rebind(self, body, selector, target, **extra):
        return {**body, "call_sites": [
            {**site, "targets": [{**row, "target_hash": target, **extra}
                                 for row in site["targets"]]}
            if site["call_site_id"] == selector else site for site in body["call_sites"]
        ]}

    def test_independent_retargets_survive_and_rebuild_the_same_export(self):
        base, left, right = self.branches(
            lambda body: self.rebind(body, "first", self.left_hash),
            lambda body: self.rebind(body, "second", self.right_hash),
        )
        result = merge_closed(base, left, right, "caller")
        swapped = merge_closed(base, right, left, "caller")
        self.assertEqual(result.export, swapped.export)
        self.assertEqual(result.selections, swapped.selections)
        self.assertEqual(result.pins, (swapped.pins[0], swapped.pins[2], swapped.pins[1]))
        exported = {row["slot"]: row["declaration"] for row in json.loads(result.export)}
        new_targets = targets(exported["caller"])
        self.assertEqual(new_targets["first", "direct"]["target_hash"], self.left_hash)
        self.assertEqual(new_targets["second", "direct"]["target_hash"], self.right_hash)

    def test_competing_retarget_fails_at_exact_selector(self):
        inventories = self.branches(
            lambda body: self.rebind(body, "first", self.left_hash),
            lambda body: self.rebind(body, "first", self.right_hash),
        )
        with self.assertRaisesRegex(CallMergeConflict, "competing retargets.*first"):
            merge_closed(*inventories, "caller")

    def test_guard_change_is_outside_retarget_policy(self):
        inventories = self.branches(
            lambda body: self.rebind(body, "first", self.left_hash, condition="new-guard"),
            lambda body: self.rebind(body, "second", self.right_hash),
        )
        with self.assertRaisesRegex(CallMergeConflict, "guard or contract.*first"):
            merge_closed(*inventories, "caller")

    def test_existing_upstream_caller_requires_explicit_old_version(self):
        inventories = self.branches(
            lambda body: self.rebind(body, "first", self.left_hash),
            lambda body: self.rebind(body, "second", self.right_hash),
            upstream=True, retain=True,
        )
        result = merge_closed(*inventories, "caller")
        selected = dict(result.selections)
        self.assertNotEqual(selected["caller"], selected["caller.old"])
        self.assertEqual(selected["upstream"], tree.import_closed(inventories[0])[1].mapping["upstream"])

    def test_both_tips_valid_but_upstream_pin_to_branch_version_blocks_merge(self):
        inventories = self.branches(
            lambda body: self.rebind(body, "first", self.left_hash),
            lambda body: self.rebind(body, "second", self.right_hash),
            branch_pin=True,
        )
        _, left = tree.import_closed(inventories[1])
        tree.import_closed(inventories[2])
        with self.assertRaisesRegex(tree.GraphImportError, left.mapping["caller"]):
            merge_closed(*inventories, "caller")
