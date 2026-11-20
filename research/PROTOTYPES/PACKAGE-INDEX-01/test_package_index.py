import unittest
from copy import deepcopy

from package_index import IndexError, logical_hash, merge, normalize

H1 = "sha256:" + "1" * 64
H2 = "sha256:" + "2" * 64
H3 = "sha256:" + "3" * 64

def index_a():
    return {
        "objects": [{"hash": H1, "kind": "function", "size": 10},
                    {"hash": H2, "kind": "interface", "size": 20}],
        "dependencies": [{"source_hash": H1, "edge_id": "dep-1", "kind": "required",
                          "target_hash": H2, "included": True}],
        "exports": [{"module_id": "mod:math", "name": "add", "object_hash": H1}],
        "modules": [{"module_id": "mod:math", "members": [H2, H1]}],
    }

def index_b():
    return {
        "objects": [{"hash": H2, "kind": "interface", "size": 20},
                    {"hash": H3, "kind": "type", "size": 30}],
        "dependencies": [{"source_hash": H3, "edge_id": "dep-1", "kind": "optional",
                          "target_hash": H2, "included": True}],
        "exports": [{"module_id": "mod:types", "name": "Number", "object_hash": H3}],
        "modules": [{"module_id": "mod:types", "members": [H3]}],
    }

class LogicalIndexTests(unittest.TestCase):
    def test_canonical_order_and_hash_ignore_input_record_order(self):
        a = index_a()
        b = deepcopy(a)
        for rows in b.values():
            rows.reverse()
        self.assertEqual(logical_hash(a), logical_hash(b))
        self.assertEqual(normalize(a), normalize(b))

    def test_merge_deduplicates_identical_objects_and_is_deterministic(self):
        ab = merge(index_a(), index_b())
        ba = merge(index_b(), index_a())
        self.assertEqual(ab, ba)
        self.assertEqual(logical_hash(ab), logical_hash(ba))
        self.assertEqual(sum(row["hash"] == H2 for row in ab["objects"]), 1)

    def test_merge_is_idempotent(self):
        self.assertEqual(merge(index_a(), index_a()), normalize(index_a()))

    def test_merge_is_associative_for_conflict_free_inputs(self):
        a, b = index_a(), index_b()
        c = {
            "objects": [{"hash": H3, "kind": "type", "size": 30}],
            "dependencies": [], "exports": [], "modules": [],
        }
        self.assertEqual(merge(merge(a, b), c), merge(a, merge(b, c)))

    def test_conflicting_same_key_record_fails(self):
        changed = deepcopy(index_a())
        changed["objects"][0]["size"] = 999
        with self.assertRaisesRegex(IndexError, "conflicting record"):
            merge(index_a(), changed)

    def test_duplicate_key_inside_one_table_fails(self):
        bad = index_a()
        bad["objects"].append(deepcopy(bad["objects"][0]))
        with self.assertRaisesRegex(IndexError, "duplicate key"):
            normalize(bad)

    def test_included_dependency_target_must_exist(self):
        bad = index_a()
        bad["dependencies"][0]["target_hash"] = H3
        with self.assertRaisesRegex(IndexError, "target is absent"):
            normalize(bad)

    def test_external_dependency_does_not_require_membership(self):
        bad = index_a()
        bad["dependencies"][0]["target_hash"] = H3
        bad["dependencies"][0]["included"] = False
        self.assertEqual(len(normalize(bad)["objects"]), 2)

    def test_module_and_export_references_are_checked(self):
        bad = index_a()
        bad["exports"][0]["module_id"] = "mod:missing"
        with self.assertRaisesRegex(IndexError, "absent module"):
            normalize(bad)

    def test_identity_change_changes_logical_hash(self):
        changed = deepcopy(index_a())
        changed["objects"][0]["size"] += 1
        self.assertNotEqual(logical_hash(index_a()), logical_hash(changed))

    def test_unknown_fields_and_wrong_scalar_types_fail_closed(self):
        bad = index_a()
        bad["objects"][0]["unexpected"] = True
        with self.assertRaises(IndexError):
            normalize(bad)
        bad = index_a()
        bad["objects"][0]["size"] = True
        with self.assertRaises(IndexError):
            normalize(bad)

if __name__ == "__main__":
    unittest.main(verbosity=2)
