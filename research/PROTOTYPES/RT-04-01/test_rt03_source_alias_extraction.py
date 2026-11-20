import unittest

from rt03_alias_sensitive_call_paths import routes_for_alias_targets
from rt03_source_alias_extraction import (
    UnsupportedSource,
    compare_source_fixture,
    extract_call_aliases,
)


TOGGLE = """\
def flip(ref):
    ref.value = not ref.value

flag = input_bool("flag")
other = input_bool("other")
choose = input_bool("choose")
target = ref(flag)
flip(target)
"""


class SourceAliasExtractionTests(unittest.TestCase):
    def test_exact_field_alias_is_extracted_from_source_ast(self):
        result = extract_call_aliases(TOGGLE)
        self.assertEqual(result.summary, "toggle")
        self.assertEqual(result.call_targets, frozenset({"flag"}))

    def test_disjoint_field_alias_matches_concrete_execution(self):
        source = TOGGLE.replace("ref(flag)", "ref(other)")
        extracted, concrete, analyzed = compare_source_fixture(source)
        self.assertEqual(extracted.call_targets, frozenset({"other"}))
        self.assertEqual(analyzed, concrete)
        self.assertEqual(concrete, frozenset({(False, False), (True, True)}))

    def test_branch_join_derives_may_alias_set_and_preserves_all_routes(self):
        source = TOGGLE.replace(
            "target = ref(flag)",
            "target = ref(flag)\nif choose:\n    target = ref(other)",
        )
        extracted, concrete, analyzed = compare_source_fixture(source)
        self.assertEqual(extracted.call_targets, frozenset({"flag", "other"}))
        self.assertEqual(analyzed, concrete)
        self.assertEqual(len(concrete), 4)

    def test_nonrelational_alias_join_is_sound_but_loses_path_correlation(self):
        source = TOGGLE.replace(
            "target = ref(flag)",
            "target = ref(flag)\nif flag:\n    target = ref(other)\nelse:\n    target = ref(flag)",
        )
        extracted, concrete, analyzed = compare_source_fixture(source)
        self.assertEqual(extracted.call_targets, frozenset({"flag", "other"}))
        self.assertTrue(concrete <= analyzed)
        self.assertGreater(len(analyzed), len(concrete))
        self.assertEqual(concrete, frozenset({(False, True), (True, True)}))

    def test_unknown_reference_is_top_over_the_declared_region(self):
        source = TOGGLE.replace("target = ref(flag)", "target = unknown_ref()")
        extracted, concrete, analyzed = compare_source_fixture(source)
        self.assertEqual(extracted.call_targets, frozenset({"flag", "other"}))
        self.assertEqual(analyzed, concrete)
        self.assertEqual(len(concrete), 4)

    def test_omitting_one_possible_alias_drops_concrete_routes(self):
        source = TOGGLE.replace(
            "target = ref(flag)",
            "target = ref(flag)\nif choose:\n    target = ref(other)",
        )
        _, concrete, _ = compare_source_fixture(source)
        incorrect = routes_for_alias_targets(frozenset({"other"}))
        self.assertFalse(concrete <= incorrect)

    def test_mutator_outside_supported_summary_fails_closed(self):
        source = TOGGLE.replace("not ref.value", "ref.value + 1")
        with self.assertRaises(UnsupportedSource):
            extract_call_aliases(source)

    def test_unmodeled_field_fails_closed(self):
        source = TOGGLE.replace("ref(flag)", "ref(hidden)")
        with self.assertRaises(UnsupportedSource):
            extract_call_aliases(source)


if __name__ == "__main__":
    unittest.main()
