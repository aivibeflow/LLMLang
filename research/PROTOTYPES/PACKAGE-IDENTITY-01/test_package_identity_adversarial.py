"""Additional parser and package-membership regression tests."""
import unittest

from package_identity import PackageFormatError, package_content_root, parse_manifest
from test_package_identity import H1, H3, manifest_text, sample_index


class ManifestAdversarialTests(unittest.TestCase):
    def setUp(self):
        self.index = sample_index()
        self.raw = manifest_text(self.index).encode()

    def test_pmi_001_table_and_key_order_are_irrelevant(self):
        original = self.raw.decode()
        blocks = original.split("\n[")
        header = blocks[0]
        reordered = [header] + ["[" + block for block in reversed(blocks[1:])]
        alt = "\n".join(reordered)
        # Also change whitespace and add comments without changing typed values.
        alt = alt.replace("schema_version = 1", "schema_version    =    1 # reordered fixture")
        self.assertEqual(
            package_content_root(parse_manifest(self.raw), self.index),
            package_content_root(parse_manifest(alt.encode()), self.index),
        )

    def test_package_root_must_be_an_included_object(self):
        bad = self.raw.decode().replace(f"'{H1}'", f"'{H3}'")
        with self.assertRaisesRegex(PackageFormatError, "root is not present"):
            package_content_root(parse_manifest(bad.encode()), self.index)

    def test_cache_indexes_must_be_an_array(self):
        bad = self.raw.decode().replace(
            'indexes = ["cache/validation.index"]',
            'indexes = "cache/validation.index"',
        )
        with self.assertRaisesRegex(PackageFormatError, "must be an array"):
            parse_manifest(bad.encode())

    def test_cache_index_paths_must_be_unique(self):
        bad = self.raw.decode().replace(
            'indexes = ["cache/validation.index"]',
            'indexes = ["cache/validation.index", "cache/validation.index"]',
        )
        with self.assertRaisesRegex(PackageFormatError, "duplicate cache index"):
            parse_manifest(bad.encode())

    def test_cache_index_must_not_collide_with_package_index(self):
        bad = self.raw.decode().replace(
            'indexes = ["cache/validation.index"]',
            'indexes = ["index.bin"]',
        )
        with self.assertRaisesRegex(PackageFormatError, "collides"):
            parse_manifest(bad.encode())

    def test_noncanonical_relative_paths_are_rejected(self):
        for path in ("./index.bin", "cache//validation.index", "cache/"):
            with self.subTest(path=path):
                bad = self.raw.decode().replace('path = "index.bin"', f'path = "{path}"')
                with self.assertRaises(PackageFormatError):
                    parse_manifest(bad.encode())

    def test_unknown_nested_package_field_is_rejected(self):
        bad = self.raw.decode().replace(
            '[package]\nname = "example-math"',
            '[package]\nunknown_identity_hint = "surprise"\nname = "example-math"',
        )
        with self.assertRaises(PackageFormatError):
            parse_manifest(bad.encode())


if __name__ == "__main__":
    unittest.main(verbosity=2)
