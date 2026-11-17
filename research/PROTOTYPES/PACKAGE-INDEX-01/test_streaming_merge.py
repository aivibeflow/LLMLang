import unittest

from package_index import IndexError, merge_sorted_indexes, merge_sorted_rows

H = lambda n: "sha256:" + format(n, "064x")

def object_row(n):
    return {"hash": H(n), "kind": "object", "size": n}

class StreamingMergeTests(unittest.TestCase):
    def test_merge_is_lazy_and_does_not_consume_all_inputs(self):
        consumed = []
        def source(values, label):
            for value in values:
                consumed.append((label, value))
                yield object_row(value)
        merged = merge_sorted_rows("objects", source([1, 3, 5], "a"), source([2, 3, 4], "b"))
        self.assertEqual(consumed, [])
        first = next(merged)
        self.assertEqual(first["hash"], H(1))
        self.assertLess(len(consumed), 6)
        self.assertEqual([row["hash"] for row in merged], [H(i) for i in range(2, 6)])

    def test_large_generated_streams_merge_without_input_lists(self):
        left = (object_row(i) for i in range(0, 20000, 2))
        right = (object_row(i) for i in range(1, 20000, 2))
        result = merge_sorted_rows("objects", left, right)
        self.assertEqual(sum(1 for _ in result), 20000)

    def test_identical_cross_stream_records_are_deduplicated(self):
        result = list(merge_sorted_rows(
            "objects",
            [object_row(1), object_row(3)],
            [object_row(1), object_row(2)],
        ))
        self.assertEqual([row["hash"] for row in result], [H(1), H(2), H(3)])

    def test_conflicting_cross_stream_records_fail(self):
        changed = object_row(2)
        changed["size"] = 999
        with self.assertRaisesRegex(IndexError, "conflicting record"):
            list(merge_sorted_rows("objects", [object_row(1), object_row(2)],
                                   [object_row(2), object_row(3)] if False else [changed]))

    def test_duplicate_key_inside_one_stream_fails(self):
        with self.assertRaisesRegex(IndexError, "duplicate key in input stream"):
            list(merge_sorted_rows("objects", [object_row(1), object_row(1)]))

    def test_unsorted_input_stream_fails(self):
        with self.assertRaisesRegex(IndexError, "not sorted"):
            list(merge_sorted_rows("objects", [object_row(2), object_row(1)]))

    def test_merge_result_is_independent_of_stream_order(self):
        a = [object_row(1), object_row(4)]
        b = [object_row(2), object_row(3)]
        ab = list(merge_sorted_rows("objects", a, b))
        ba = list(merge_sorted_rows("objects", b, a))
        self.assertEqual(ab, ba)

    def test_streamed_index_exposes_lazy_table_iterators(self):
        a = {"objects": [object_row(1)], "dependencies": [], "exports": [], "modules": []}
        b = {"objects": [object_row(2)], "dependencies": [], "exports": [], "modules": []}
        merged = merge_sorted_indexes([a, b])
        self.assertEqual([r["hash"] for r in merged["objects"]], [H(1), H(2)])
        self.assertEqual(list(merged["dependencies"]), [])

    def test_unknown_table_and_empty_stream_list_fail(self):
        with self.assertRaises(IndexError):
            list(merge_sorted_rows("unknown", []))
        with self.assertRaises(IndexError):
            list(merge_sorted_rows("objects"))

if __name__ == "__main__":
    unittest.main(verbosity=2)
