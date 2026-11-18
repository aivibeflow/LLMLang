import unittest
from rt04_model import check_program, ModelError

class RT04ModelTests(unittest.TestCase):
    def test_profile_a_accepts_primitive_signature_and_closed_effect(self):
        p = {"functions": {"read_config": {"params": {"path": "String"}, "result": "String", "effects": ["fs.read"]}}}
        self.assertEqual(check_program(p, "A").status, "ACCEPTED")

    def test_profile_a_rejects_open_effect_row(self):
        p = {"functions": {"f": {"effect_row": "e"}}}
        self.assertIn("OPEN_EFFECT_ROW_UNSUPPORTED", check_program(p, "A").codes())

    def test_profile_b_accepts_open_effect_row(self):
        p = {"functions": {"f": {"effects": ["fs.read"], "effect_row": "e"}}}
        self.assertEqual(check_program(p, "B").status, "ACCEPTED")

    def test_refinement_positive_negative_and_unknown_are_distinct(self):
        base = {"functions": {"f": {"params": {"amount": "Int"}, "positive_params": ["amount"]}}}
        positive = {"functions": {"f": {**base["functions"]["f"], "known_values": {"amount": 7}}}}
        negative = {"functions": {"f": {**base["functions"]["f"], "known_values": {"amount": -2}}}}
        self.assertEqual(check_program(positive, "B").status, "ACCEPTED")
        self.assertIn("REFINEMENT_DISPROVEN", check_program(negative, "B").codes())
        self.assertEqual(check_program(base, "B").status, "UNKNOWN")
        self.assertIn("REFINEMENT_UNSUPPORTED", check_program(base, "A").codes())

    def test_effects_propagate_transitively(self):
        p = {"functions": {"entry": {"calls": ["load"]}, "load": {"calls": ["read"]}, "read": {"effects": ["fs.read"]}}}
        result = check_program(p, "B")
        self.assertEqual(dict(result.inferred_effects)["entry"], ("fs.read",))

    def test_capability_is_propagated_to_caller_in_profile_b(self):
        p = {"functions": {"entry": {"calls": ["send"]}, "send": {"requires": ["network.send"]}}}
        result = check_program(p, "B")
        self.assertIn("CAPABILITY_NOT_DECLARED", result.codes())
        p["functions"]["entry"]["requires"] = ["network.send"]
        self.assertEqual(check_program(p, "B").status, "ACCEPTED")

    def test_profile_a_uses_ambient_capability_context(self):
        p = {"ambient_capabilities": ["network.send"], "functions": {"send": {"requires": ["network.send"]}}}
        self.assertEqual(check_program(p, "A").status, "ACCEPTED")

    def test_affine_profile_rejects_double_consumption(self):
        p = {"resources": {"socket": "owned"}, "functions": {"f": {"consumes": ["socket", "socket"]}}}
        self.assertIn("RESOURCE_USE_AFTER_MOVE", check_program(p, "B").codes())
        self.assertEqual(check_program(p, "A").status, "ACCEPTED")

    def test_affine_profile_rejects_unknown_resource(self):
        p = {"functions": {"f": {"consumes": ["missing"]}}}
        self.assertIn("UNKNOWN_RESOURCE", check_program(p, "B").codes())

    def test_unknown_callee_fails_closed(self):
        p = {"functions": {"entry": {"calls": ["missing"]}}}
        self.assertIn("UNKNOWN_CALLEE", check_program(p, "B").codes())

    def test_unknown_effect_rejected_by_closed_profile(self):
        p = {"functions": {"f": {"effects": ["gpu.launch"]}}}
        self.assertIn("UNKNOWN_EFFECT", check_program(p, "A").codes())

    def test_rejects_malformed_envelope(self):
        with self.assertRaises(ModelError):
            check_program({"functions": {"f": {}}, "extra": 1}, "A")

if __name__ == "__main__":
    unittest.main()
