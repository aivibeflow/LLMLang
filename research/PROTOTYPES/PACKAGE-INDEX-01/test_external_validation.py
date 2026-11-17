import unittest

from package_index import IndexError, normalize, validate_streamed_index

H = lambda n: "sha256:" + format(n, "064x")

def valid_index():
    return normalize({
        "objects": [
            {"hash": H(1), "kind": "function", "size": 10},
            {"hash": H(2), "kind": "type", "size": 20},
            {"hash": H(3), "kind": "evidence", "size": 30},
        ],
        "dependencies": [
            {"source_hash": H(1), "edge_id": "dep-a", "kind": "required",
             "target_hash": H(2), "included": True},
            {"source_hash": H(2), "edge_id": "dep-b", "kind": "optional",
             "target_hash": H(99), "included": False},
        ],
        "exports": [
            {"module_id": "mod:a", "name": "first", "object_hash": H(1)},
            {"module_id": "mod:b", "name": "second", "object_hash": H(3)},
        ],
        "modules": [
            {"module_id": "mod:a", "members": [H(1), H(2)]},
            {"module_id": "mod:b", "members": [H(3)]},
        ],
    })

def streamed(index):
    return {name: (row for row in index[name]) for name in index}

class ExternalValidationTests(unittest.TestCase):
    def test_valid_index_passes_with_tiny_external_sort_runs(self):
        self.assertTrue(validate_streamed_index(streamed(valid_index()), max_records_in_memory=1))

    def test_missing_dependency_source_fails(self):
        index = valid_index()
        index["dependencies"][0]["source_hash"] = H(88)
        index["dependencies"].sort(key=lambda r: (r["source_hash"], r["edge_id"]))
        with self.assertRaisesRegex(IndexError, "dependency source"):
            validate_streamed_index(streamed(index), max_records_in_memory=2)

    def test_missing_included_dependency_target_fails(self):
        index = valid_index()
        index["dependencies"][0]["target_hash"] = H(88)
        with self.assertRaisesRegex(IndexError, "dependency target"):
            validate_streamed_index(streamed(index), max_records_in_memory=1)

    def test_external_dependency_target_need_not_be_in_objects(self):
        self.assertTrue(validate_streamed_index(streamed(valid_index()), max_records_in_memory=1))

    def test_missing_module_member_fails(self):
        index = valid_index()
        index["modules"][0]["members"].append(H(77))
        with self.assertRaisesRegex(IndexError, "module references"):
            validate_streamed_index(streamed(index), max_records_in_memory=1)

    def test_missing_export_module_fails(self):
        index = valid_index()
        index["exports"][0]["module_id"] = "mod:missing"
        index["exports"].sort(key=lambda r: (r["module_id"], r["name"]))
        with self.assertRaisesRegex(IndexError, "absent module"):
            validate_streamed_index(streamed(index), max_records_in_memory=1)

    def test_missing_export_object_fails(self):
        index = valid_index()
        index["exports"][0]["object_hash"] = H(78)
        with self.assertRaisesRegex(IndexError, "export references an absent object"):
            validate_streamed_index(streamed(index), max_records_in_memory=1)

    def test_unsorted_table_is_rejected(self):
        index = valid_index()
        index["objects"].reverse()
        with self.assertRaisesRegex(IndexError, "not sorted"):
            validate_streamed_index(streamed(index))

    def test_duplicate_table_key_is_rejected(self):
        index = valid_index()
        first = dict(index["objects"][0])
        index["objects"] = [first, dict(first)] + index["objects"][1:]
        with self.assertRaisesRegex(IndexError, "duplicate key"):
            validate_streamed_index(streamed(index))

    def test_invalid_memory_bound_is_rejected(self):
        with self.assertRaisesRegex(IndexError, "positive integer"):
            validate_streamed_index(streamed(valid_index()), max_records_in_memory=0)

if __name__ == "__main__":
    unittest.main(verbosity=2)
