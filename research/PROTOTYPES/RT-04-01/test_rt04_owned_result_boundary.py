"""Capability probes for owned resource result shapes at typed call boundaries."""
import unittest

from rt04_model import check_program


class OwnedResultBoundary(unittest.TestCase):
    def test_existing_primitive_result_call_is_the_supported_control(self):
        result_type = {"Result": ["String", "String"]}
        program = {"functions": {
            "caller": {"calls": ["factory"], "call_sites": [
                {"target": "factory", "args": [], "expected_result": result_type},
            ]},
            "factory": {"params": {}, "result": result_type},
        }}
        self.assertEqual(check_program(program, "B").status, "ACCEPTED")

    def test_nested_owned_result_is_unknown_to_rt04(self):
        result_type = {"Result": [{"Owned": "Handle"}, "String"]}
        program = {"functions": {
            "caller": {"calls": ["factory"], "call_sites": [
                {"target": "factory", "args": [], "expected_result": result_type},
            ]},
            "factory": {"params": {}, "result": result_type},
        }}
        result = check_program(program, "B")
        self.assertEqual(result.status, "REJECTED")
        self.assertIn("UNKNOWN_TYPE", result.codes())

    def test_error_with_value_result_constructor_is_unknown_to_rt04(self):
        result_type = {"ErrorWithValue": [
            {"Owned": "Handle"}, "String", "CleanupError",
        ]}
        program = {"functions": {
            "caller": {"calls": ["factory"], "call_sites": [
                {"target": "factory", "args": [], "expected_result": result_type},
            ]},
            "factory": {"params": {}, "result": result_type},
        }}
        result = check_program(program, "B")
        self.assertEqual(result.status, "REJECTED")
        self.assertIn("UNKNOWN_TYPE", result.codes())

    def test_typed_call_projection_rejects_owned_result_signature(self):
        import sys
        if sys.version_info < (3, 10):
            self.skipTest("rt03_typed_calls requires Python 3.10+ structural pattern matching")
        from rt03_typed_calls import FragmentError, Function, project_program
        with self.assertRaisesRegex(FragmentError, "supported signature"):
            project_program({
                "caller": Function((), "Unit", {"literal": None}),
                "factory": Function((), "OwnedHandle", {"literal": "handle"}),
            }, "B")


if __name__ == "__main__":
    unittest.main()
