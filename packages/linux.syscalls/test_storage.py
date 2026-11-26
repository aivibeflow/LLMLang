from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import storage


class PackageStorageTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "package"
        self.records = {
            "linux.syscalls.write": {
                "types": ["BorrowedFd", "Bytes"],
                "metadata": {"count": -1, "nullable": None, "enabled": False},
                "source": "x" * 4096,
            },
            "linux.syscalls.read": {
                "bounds": [-(1 << 63), (1 << 63) - 1],
                "metadata": {"empty-array": [], "empty-object": {}},
            },
        }
        self.index = storage.export_records(self.records, self.path)

    def test_checkout_is_deterministic_and_each_range_is_readable(self):
        other = self.path.with_name("other")
        storage.export_records(dict(reversed(self.records.items())), other)
        for name in (storage.INDEX, storage.DUMP):
            self.assertEqual((self.path / name).read_bytes(), (other / name).read_bytes())
        self.assertEqual(storage.verify_records(self.path), self.index)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                key: executor.submit(storage.load_record, self.path, key)
                for key in self.records
            }
            self.assertEqual({key: future.result() for key, future in futures.items()}, self.records)
        self.assertLess(self.index["linux.syscalls.write"]["compressed_length"], 4096)

    def test_missing_invalid_and_mismatched_index_rebuild_to_exact_bytes(self):
        index_path = self.path / storage.INDEX
        original = index_path.read_bytes()
        key = "linux.syscalls.read"
        for data in (None, b"invalid"):
            with self.subTest(data=data):
                if data is None:
                    index_path.unlink()
                else:
                    index_path.write_bytes(data)
                self.assertEqual(storage.load_record(self.path, key), self.records[key])
                self.assertEqual(index_path.read_bytes(), original)
        index_path.write_bytes(original.replace(key.encode(), b"linux.syscalls.fake"))
        with self.assertRaisesRegex(storage.StorageError, "absent"):
            storage.load_record(self.path, "linux.syscalls.fake")
        self.assertEqual(index_path.read_bytes(), original)
        index_path.write_bytes(original.replace(key.encode(), b"linux.syscalls.fake"))
        self.assertEqual(storage.load_record(self.path, key), self.records[key])
        self.assertEqual(index_path.read_bytes(), original)

    def test_cache_hits_do_not_open_the_dump_and_require_exact_content(self):
        cache = {}
        key = "linux.syscalls.read"
        original = storage.load_record(self.path, key, cache=cache)
        open_path = Path.open

        def forbid_dump(path, *args, **kwargs):
            if path.name == storage.DUMP:
                raise AssertionError("opened data file")
            return open_path(path, *args, **kwargs)

        with patch.object(Path, "open", forbid_dump):
            self.assertEqual(storage.load_record(self.path, key, cache=cache), original)
            cache[self.index[key]["content_hash"]] = {"tampered": 1}
            with self.assertRaisesRegex(storage.StorageError, "cached record content hash"):
                storage.load_record(self.path, key, cache=cache)

    def test_later_range_is_independent_of_earlier_corruption(self):
        dump = self.path / storage.DUMP
        key = "linux.syscalls.read"
        payload = bytearray(dump.read_bytes())
        payload[self.index[key]["offset"] - 1] ^= 1
        dump.write_bytes(payload)
        other = "linux.syscalls.write"
        self.assertEqual(storage.load_record(self.path, other), self.records[other])
        with self.assertRaisesRegex(storage.StorageError, "content hash mismatch"):
            storage.verify_records(self.path)
        with self.assertRaises(storage.StorageError):
            storage.rebuild_index(self.path)
        with self.assertRaises(storage.StorageError):
            storage.load_record(self.path, key)

    def test_bad_index_range_and_bad_record_shape_fail_closed(self):
        index_path = self.path / storage.INDEX
        index = json.loads(index_path.read_bytes())
        index["entries"]["linux.syscalls.read"]["offset"] = True
        index_path.write_text(json.dumps(index), encoding="utf-8")
        with self.assertRaises(storage.StorageError):
            storage.verify_records(self.path)
        self.assertEqual(storage.rebuild_index(self.path), self.index)
        with self.assertRaises(storage.StorageError):
            storage.export_records({"invalid": {"huge": 1 << 63}}, self.path)
        self.assertEqual(storage.verify_records(self.path), self.index)


if __name__ == "__main__":
    unittest.main()
