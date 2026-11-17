import hashlib
import io
import os
import tempfile
import unittest
import zipfile

from package_archive import ArchiveError, build_archive, verify_archive
from package_index import normalize

H1 = "sha256:" + hashlib.sha256(b"alpha").hexdigest()
H2 = "sha256:" + hashlib.sha256(b"beta").hexdigest()


def sample_index():
    return normalize({
        "objects": [
            {"hash": H1, "kind": "function", "size": 5},
            {"hash": H2, "kind": "type", "size": 4},
        ],
        "dependencies": [
            {"source_hash": H1, "edge_id": "dep-1", "kind": "required",
             "target_hash": H2, "included": True},
        ],
        "exports": [
            {"module_id": "mod:sample", "name": "alpha", "object_hash": H1},
        ],
        "modules": [
            {"module_id": "mod:sample", "members": [H1, H2]},
        ],
    })


def streams(index):
    return {table: (row for row in index[table]) for table in index}


def payloads(order=(H1, H2)):
    values = {H1: b"alpha", H2: b"beta"}
    return ((content_hash, io.BytesIO(values[content_hash])) for content_hash in order)


class StreamingArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "sample.llpkg")
        self.manifest = b'format = "llmlang.package"\nschema_version = 1\n'

    def tearDown(self):
        self.temp.cleanup()

    def build(self, path=None, object_order=(H1, H2), index=None):
        return build_archive(
            self.manifest,
            streams(index or sample_index()),
            payloads(object_order),
            path or self.path,
            max_records_in_memory=1,
        )

    def test_build_and_verify(self):
        self.build()
        self.assertTrue(verify_archive(self.path, max_records_in_memory=1))

    def test_archive_is_byte_deterministic(self):
        second = os.path.join(self.temp.name, "second.llpkg")
        self.build()
        self.build(second)
        with open(self.path, "rb") as first, open(second, "rb") as other:
            self.assertEqual(first.read(), other.read())

    def test_object_hash_mismatch_fails_and_does_not_replace_destination(self):
        with open(self.path, "wb") as target:
            target.write(b"existing")
        bad = ((H1, io.BytesIO(b"wrong")), (H2, io.BytesIO(b"beta")))
        with self.assertRaisesRegex(ArchiveError, "Content Hash mismatch"):
            build_archive(self.manifest, streams(sample_index()), bad, self.path)
        with open(self.path, "rb") as target:
            self.assertEqual(target.read(), b"existing")

    def test_object_size_mismatch_fails(self):
        index = sample_index()
        index["objects"][0]["size"] = 99
        with self.assertRaisesRegex(ArchiveError, "size mismatch"):
            self.build(index=index)

    def test_missing_or_extra_payload_fails(self):
        with self.assertRaisesRegex(ArchiveError, "missing object payload"):
            build_archive(self.manifest, streams(sample_index()), payloads((H1,)), self.path)
        with self.assertRaisesRegex(ArchiveError, "stream mismatch"):
            build_archive(self.manifest, streams(sample_index()), payloads((H2, H1)), self.path)

    def test_unsorted_or_invalid_index_fails(self):
        index = sample_index()
        index["objects"].reverse()
        with self.assertRaisesRegex(ArchiveError, "not sorted"):
            self.build(index=index)

    def test_verifier_detects_corrupt_object(self):
        self.build()
        corrupt = os.path.join(self.temp.name, "corrupt.llpkg")
        with zipfile.ZipFile(self.path, "r") as source, zipfile.ZipFile(corrupt, "w") as target:
            for info in source.infolist():
                data = source.read(info.filename)
                if info.filename == f"objects/{H1.split(':')[1]}":
                    data = b"xxxxx"
                target.writestr(info, data)
        with self.assertRaisesRegex(ArchiveError, "Content Hash mismatch"):
            verify_archive(corrupt)

    def test_verifier_rejects_unexpected_entry(self):
        self.build()
        altered = os.path.join(self.temp.name, "extra.llpkg")
        with zipfile.ZipFile(self.path, "r") as source, zipfile.ZipFile(altered, "w") as target:
            for info in source.infolist():
                target.writestr(info, source.read(info.filename))
            target.writestr("unexpected.txt", b"x")
        with self.assertRaisesRegex(ArchiveError, "unexpected entries"):
            verify_archive(altered)

    def test_invalid_manifest_utf8_fails(self):
        with self.assertRaisesRegex(ArchiveError, "valid UTF-8"):
            build_archive(bytes([0xff]), streams(sample_index()), payloads(), self.path)

    def test_invalid_memory_bound_fails(self):
        with self.assertRaisesRegex(ArchiveError, "positive integer"):
            build_archive(self.manifest, streams(sample_index()), payloads(), self.path,
                          max_records_in_memory=0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
