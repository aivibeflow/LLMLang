import copy
import unittest
from package_identity import PackageFormatError, canonical, logical_index_hash, package_content_root, parse_manifest, verify_manifest

H1, H2, H3 = ("sha256:" + x * 64 for x in "123")

def sample_index():
    return {
        "objects": [{"hash": H1, "kind": "function"}, {"hash": H2, "kind": "interface"}],
        "dependencies": [{"from": H1, "kind": "required", "to": H2}],
        "exports": [{"name": "add", "object": H1}],
        "modules": [{"module": "math", "object": H1}, {"module": "math", "object": H2}],
    }

def manifest_text(index, *, name="example-math", version="0.1.0", roots=None, cache=True):
    roots = roots or [H1]
    ih = logical_index_hash(index)
    text = f'''format = "llmlang.package"
schema_version = 1

[package]
name = "{name}"
version = "{version}"

[content]
roots = [{", ".join(repr(x) for x in roots)}]
dependency_policy = "closure"
content_root = "sha256:{ "0" * 64 }"

[index]
path = "index.bin"
format_version = 1
logical_hash = "{ih}"
'''
    if cache: text += '\\n[cache]\\nindexes = ["cache/validation.index"]\\n'
    parsed = parse_manifest(text.encode())
    root = package_content_root(parsed, index)
    return text.replace("sha256:" + "0" * 64, root)

class CanonicalEncodingTests(unittest.TestCase):
    def test_types_are_distinct(self):
        self.assertNotEqual(canonical(1), canonical("1"))
        self.assertNotEqual(canonical(True), canonical(1))
        self.assertNotEqual(canonical(None), canonical(False))
    def test_map_order_is_irrelevant(self):
        self.assertEqual(canonical({"a": 1, "b": 2}), canonical({"b": 2, "a": 1}))
    def test_unsupported_float_is_rejected(self):
        with self.assertRaises(PackageFormatError): canonical(1.25)

class PackageIdentityInvariants(unittest.TestCase):
    def setUp(self):
        self.index = sample_index()
        self.raw = manifest_text(self.index).encode()
    def test_pmi_001_toml_formatting_does_not_change_root(self):
        alt = self.raw.decode().replace("schema_version = 1", "# comment\\nschema_version = 1") + "\\n# trailing comment\\n"
        self.assertEqual(verify_manifest(self.raw, self.index), verify_manifest(alt.encode(), self.index))
    def test_pmi_002_root_order_does_not_change_root(self):
        a = manifest_text(self.index, roots=[H1, H2]).encode()
        b = manifest_text(self.index, roots=[H2, H1]).encode()
        self.assertEqual(verify_manifest(a, self.index), verify_manifest(b, self.index))
    def test_pmi_003_unordered_table_record_order_does_not_change_index_hash(self):
        self.assertEqual(logical_index_hash(self.index), logical_index_hash({k: list(reversed(v)) for k, v in self.index.items()}))
    def test_pmi_004_included_object_change_changes_index_hash(self):
        changed = copy.deepcopy(self.index); changed["objects"].append({"hash": H3, "kind": "constant"})
        self.assertNotEqual(logical_index_hash(self.index), logical_index_hash(changed))
    def test_pmi_005_dependency_change_changes_index_hash(self):
        changed = copy.deepcopy(self.index); changed["dependencies"][0]["to"] = H3
        self.assertNotEqual(logical_index_hash(self.index), logical_index_hash(changed))
    def test_pmi_006_export_or_module_change_changes_index_hash(self):
        for table, field, value in [("exports", "name", "sum"), ("modules", "module", "numeric")]:
            changed = copy.deepcopy(self.index); changed[table][0][field] = value
            self.assertNotEqual(logical_index_hash(self.index), logical_index_hash(changed))
    def test_pmi_007_descriptive_metadata_is_excluded(self):
        a = manifest_text(self.index, name="one", version="1.0.0").encode()
        b = manifest_text(self.index, name="two", version="9.9.9").encode()
        self.assertEqual(verify_manifest(a, self.index), verify_manifest(b, self.index))
    def test_pmi_008_index_path_and_physical_layout_are_not_identity_inputs(self):
        relocated = self.raw.decode().replace('path = "index.bin"', 'path = "indexes/packed-zstd-v2.bin"')
        self.assertEqual(verify_manifest(self.raw, self.index), verify_manifest(relocated.encode(), self.index))
        self.assertNotEqual(b"uncompressed-index", b"zstd-blocks-index")
        self.assertEqual(logical_index_hash(self.index), logical_index_hash(copy.deepcopy(self.index)))
    def test_pmi_009_cache_indexes_are_excluded(self):
        self.assertEqual(verify_manifest(manifest_text(self.index, cache=False).encode(), self.index),
                         verify_manifest(manifest_text(self.index, cache=True).encode(), self.index))
    def test_pmi_010_provenance_sidecar_is_outside_identity_inputs(self):
        before = verify_manifest(self.raw, self.index)
        provenance_a = b'{"provider":"node-a","timestamp":"2026-01-01T00:00:00Z"}'
        provenance_b = b'{"provider":"node-b","timestamp":"2027-01-01T00:00:00Z"}'
        self.assertNotEqual(provenance_a, provenance_b)
        self.assertEqual(before, verify_manifest(self.raw, self.index))
    def test_pmi_011_declared_index_hash_mismatch_is_rejected(self):
        bad = self.raw.decode().replace(logical_index_hash(self.index), "sha256:" + "f" * 64)
        with self.assertRaises(PackageFormatError): verify_manifest(bad.encode(), self.index)
    def test_pmi_012_dependency_target_change_invalidates_declared_index_hash(self):
        changed = copy.deepcopy(self.index); changed["dependencies"][0]["to"] = H3
        with self.assertRaises(PackageFormatError): verify_manifest(self.raw, changed)
    def test_pmi_013_invalid_manifest_values_are_rejected(self):
        variants = [
            self.raw.decode().replace(f"roots = ['{H1}']", f"roots = ['{H1}', '{H1}']"),
            self.raw.decode().replace("schema_version = 1", "schema_version = 99"),
            self.raw.decode().replace('path = "index.bin"', 'path = "../index.bin"'),
            self.raw.decode().replace("schema_version = 1", "schema_version = 1\\nschema_version = 1"),
        ]
        for bad in variants:
            with self.subTest(bad=bad), self.assertRaises(PackageFormatError): parse_manifest(bad.encode())
    def test_pmi_014_static_and_dynamic_equivalent_materializations_share_root(self):
        static = manifest_text(self.index, roots=[H1, H2]).encode()
        dynamic = manifest_text(copy.deepcopy(self.index), roots=[H2, H1]).encode()
        self.assertEqual(verify_manifest(static, self.index), verify_manifest(dynamic, self.index))

if __name__ == "__main__": unittest.main(verbosity=2)
