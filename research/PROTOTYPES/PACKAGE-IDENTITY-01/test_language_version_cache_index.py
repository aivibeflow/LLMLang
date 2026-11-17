import copy
import unittest
from package_identity import PackageFormatError
from language_version import LanguageVersionError, load_component_registry, parse_language_version, registry_digest, validate_registry_extension
from cache_index import expected_action_key, validate_cache_index

COMPONENTS = ("syntax", "core_semantics", "type_system", "effects_execution", "modules_packages")
H1, H2, H3 = ("sha256:" + c * 64 for c in "123")

def sample_record(**changes):
    record = {
        "action_key": H1, "action_kind": "type_check", "action_implementation": H1,
        "input_hashes": [H2], "language_version": "1.3.2.1.0",
        "language_component_registry_digest": registry_digest(COMPONENTS),
        "toolchain_identity": H3, "target_profile_digest": H1,
        "configuration_digest": H2, "runtime_identity": H3,
        "status": "success", "determinism": "byte_deterministic",
        "dependency_complete": True, "output_artifacts": [H1],
    }
    record.update(changes)
    record["action_key"] = expected_action_key(record)
    return record

class LanguageVersionTests(unittest.TestCase):
    def test_registry_contains_only_ordered_component_ids(self):
        self.assertEqual(load_component_registry(b'components = ["syntax", "core_semantics"]'), ("syntax", "core_semantics"))
    def test_registry_rejects_extra_metadata_and_duplicates(self):
        for raw in (b'components = ["syntax", "syntax"]', b'components = ["syntax"]\nversion = "1"'):
            with self.subTest(raw=raw), self.assertRaises(LanguageVersionError):
                load_component_registry(raw)
    def test_registry_digest_ignores_toml_formatting(self):
        a = load_component_registry(b'components=["syntax","type_system"]')
        b = load_component_registry(b'# comment\ncomponents = [ "syntax", "type_system" ]\n')
        self.assertEqual(registry_digest(a), registry_digest(b))
    def test_old_version_is_zero_extended_after_append(self):
        self.assertEqual(parse_language_version("1.2", COMPONENTS), (1, 2, 0, 0, 0))
    def test_version_rejects_noncanonical_and_excess_coordinates(self):
        for value in ("01.2", "-1.2", "1..2", "1.2.3.4.5.6", "1.0.0-beta"):
            with self.subTest(value=value), self.assertRaises(LanguageVersionError):
                parse_language_version(value, COMPONENTS)
    def test_registry_extension_must_preserve_exact_prefix(self):
        validate_registry_extension(COMPONENTS, COMPONENTS + ("concurrency",))
        for invalid in (("syntax", "type_system"), COMPONENTS[:-1] + ("other",)):
            with self.subTest(invalid=invalid), self.assertRaises(LanguageVersionError):
                validate_registry_extension(COMPONENTS, invalid)

class CacheIndexTests(unittest.TestCase):
    def valid_index(self):
        return {"schema": "llmlang.cache-index", "schema_version": 1, "records": [sample_record()]}
    def test_valid_record_is_accepted(self):
        self.assertEqual(validate_cache_index(self.valid_index(), COMPONENTS)["schema"], "llmlang.cache-index")
    def test_language_version_changes_action_key(self):
        a = sample_record(); b = copy.deepcopy(a); b["language_version"] = "1.3.3.1.0"
        self.assertNotEqual(a["action_key"], expected_action_key(b))
    def test_registry_digest_changes_action_key(self):
        a = sample_record(); b = copy.deepcopy(a); b["language_component_registry_digest"] = H2
        self.assertNotEqual(a["action_key"], expected_action_key(b))
    def test_toolchain_identity_changes_action_key(self):
        a = sample_record(); b = copy.deepcopy(a); b["toolchain_identity"] = H1
        self.assertNotEqual(a["action_key"], expected_action_key(b))
    def test_action_key_mismatch_is_rejected(self):
        data = self.valid_index(); data["records"][0]["action_key"] = H2
        with self.assertRaisesRegex(PackageFormatError, "does not match"):
            validate_cache_index(data, COMPONENTS)
    def test_incomplete_or_transient_results_are_rejected(self):
        for field, value in (("dependency_complete", False), ("status", "timeout")):
            data = self.valid_index(); data["records"][0][field] = value
            data["records"][0]["action_key"] = expected_action_key(data["records"][0])
            with self.subTest(field=field), self.assertRaises(PackageFormatError):
                validate_cache_index(data, COMPONENTS)
    def test_unknown_fields_and_duplicate_keys_are_rejected(self):
        data = self.valid_index(); data["records"][0]["unrecognized"] = True
        with self.assertRaises(PackageFormatError):
            validate_cache_index(data, COMPONENTS)
        data = self.valid_index(); data["records"].append(copy.deepcopy(data["records"][0]))
        with self.assertRaisesRegex(PackageFormatError, "duplicate Action Key"):
            validate_cache_index(data, COMPONENTS)
    def test_records_must_be_sorted(self):
        a, b = sample_record(action_kind="a"), sample_record(action_kind="b")
        data = {"schema": "llmlang.cache-index", "schema_version": 1, "records": [b, a]}
        with self.assertRaisesRegex(PackageFormatError, "sorted"):
            validate_cache_index(data, COMPONENTS)

if __name__ == "__main__":
    unittest.main(verbosity=2)
