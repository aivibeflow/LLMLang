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

    def test_branch_paths_that_agree_at_join_are_accepted(self):
        p = {
            "resources": {"socket": "owned"},
            "functions": {"f": {"resource_flow": {
                "entry": "branch",
                "blocks": {
                    "branch": {"successors": ["left", "right"]},
                    "left": {"ops": [{"consume": "socket"}], "successors": ["join"]},
                    "right": {"ops": [{"consume": "socket"}], "successors": ["join"]},
                    "join": {},
                },
            }}},
        }
        self.assertEqual(check_program(p, "B").status, "ACCEPTED")

    def test_branch_join_rejects_inconsistent_resource_state(self):
        p = {
            "resources": {"socket": "owned"},
            "functions": {"f": {"resource_flow": {
                "entry": "branch",
                "blocks": {
                    "branch": {"successors": ["left", "right"]},
                    "left": {"ops": [{"consume": "socket"}], "successors": ["join"]},
                    "right": {"successors": ["join"]},
                    "join": {},
                },
            }}},
        }
        result = check_program(p, "B")
        self.assertIn("RESOURCE_STATE_MISMATCH", result.codes())
        self.assertEqual(result.status, "REJECTED")

    def test_branch_local_double_consumption_is_rejected(self):
        p = {
            "resources": {"socket": "owned"},
            "functions": {"f": {"resource_flow": {
                "entry": "entry",
                "blocks": {
                    "entry": {"ops": [{"consume": "socket"}, {"consume": "socket"}]},
                },
            }}},
        }
        self.assertIn("RESOURCE_USE_AFTER_MOVE", check_program(p, "B").codes())

    def test_loop_reconsumption_is_rejected(self):
        p = {
            "resources": {"token": "owned"},
            "functions": {"f": {"resource_flow": {
                "entry": "loop",
                "blocks": {"loop": {"ops": [{"consume": "token"}], "successors": ["loop"]}},
            }}},
        }
        self.assertIn("RESOURCE_USE_AFTER_MOVE", check_program(p, "B").codes())

    def test_resource_flow_rejects_unknown_block_reference(self):
        p = {"functions": {"f": {"resource_flow": {
            "entry": "entry", "blocks": {"entry": {"successors": ["missing"]}},
        }}}}
        with self.assertRaises(ModelError):
            check_program(p, "B")

    def test_resource_flow_and_linear_consumes_are_mutually_exclusive(self):
        p = {"resources": {"r": "owned"}, "functions": {"f": {
            "consumes": ["r"], "resource_flow": {"entry": "entry", "blocks": {"entry": {}}},
        }}}
        with self.assertRaises(ModelError):
            check_program(p, "B")

    def test_unknown_callee_fails_closed(self):
        p = {"functions": {"entry": {"calls": ["missing"]}}}
        self.assertIn("UNKNOWN_CALLEE", check_program(p, "B").codes())

    def test_unknown_effect_requires_open_row_in_profile_b(self):
        p = {"functions": {"f": {"effects": ["gpu.launch"]}}}
        self.assertIn("UNKNOWN_EFFECT", check_program(p, "A").codes())
        self.assertIn("UNKNOWN_EFFECT", check_program(p, "B").codes())
        p["functions"]["f"]["effect_row"] = "e"
        self.assertEqual(check_program(p, "B").status, "ACCEPTED")

    def test_effect_bound_accepts_exact_transitive_effect_set(self):
        p = {
            "call_graph_complete": ["entry", "load", "read"],
            "functions": {
                "entry": {"calls": ["load"], "effect_bound": ["fs.read"]},
                "load": {"calls": ["read"]},
                "read": {"effects": ["fs.read"]},
            },
        }
        self.assertEqual(check_program(p, "B").status, "ACCEPTED")

    def test_effect_bound_rejects_transitive_effect_outside_contract(self):
        p = {
            "call_graph_complete": ["entry", "load", "send"],
            "functions": {
                "entry": {"calls": ["load"], "effect_bound": ["fs.read"]},
                "load": {"calls": ["send"], "effects": ["fs.read"]},
                "send": {"effects": ["net.send"]},
            },
        }
        result = check_program(p, "B")
        self.assertIn("EFFECT_BOUND_EXCEEDED", result.codes())
        self.assertEqual(result.status, "REJECTED")

    def test_effect_bound_accepts_multiple_declared_effects(self):
        p = {
            "call_graph_complete": ["f"],
            "functions": {"f": {"effects": ["fs.read", "net.send"], "effect_bound": ["fs.read", "net.send"]}},
        }
        self.assertEqual(check_program(p, "A").status, "ACCEPTED")

    def test_effect_bound_is_unknown_without_completeness_evidence(self):
        p = {
            "functions": {
                "entry": {"calls": ["leaf"], "effect_bound": ["fs.read"]},
                "leaf": {"effects": ["fs.read"]},
            },
        }
        result = check_program(p, "B")
        self.assertIn("EFFECT_SUMMARY_UNKNOWN", result.codes())
        self.assertEqual(result.status, "UNKNOWN")

    def test_omitted_call_edge_requires_unknown_not_empty_summary(self):
        # The explicit completeness set is the evidence boundary. A function
        # with no listed outgoing calls but no completeness evidence cannot
        # be treated as effect-free.
        p = {
            "call_graph_complete": [],
            "functions": {"entry": {"effect_bound": [], "effects": []}},
        }
        result = check_program(p, "B")
        self.assertIn("EFFECT_SUMMARY_UNKNOWN", result.codes())
        self.assertEqual(result.status, "UNKNOWN")

    def test_unknown_callee_makes_effect_bound_unknown(self):
        p = {
            "call_graph_complete": ["entry"],
            "functions": {"entry": {"calls": ["dynamic_target"], "effect_bound": []}},
        }
        result = check_program(p, "B")
        self.assertIn("UNKNOWN_CALLEE", result.codes())
        self.assertIn("EFFECT_SUMMARY_UNKNOWN", result.codes())
        self.assertEqual(result.status, "UNKNOWN")

    def test_effect_bound_requires_complete_transitive_closure(self):
        p = {
            "call_graph_complete": ["entry", "middle"],
            "functions": {
                "entry": {"calls": ["middle"], "effect_bound": ["process.spawn"]},
                "middle": {"calls": ["leaf"]},
                "leaf": {"effects": ["process.spawn"]},
            },
        }
        result = check_program(p, "B")
        self.assertIn("EFFECT_SUMMARY_UNKNOWN", result.codes())
        self.assertNotIn("EFFECT_BOUND_EXCEEDED", result.codes())
        self.assertEqual(result.status, "UNKNOWN")

    def test_known_effect_violation_rejects_even_if_graph_is_incomplete(self):
        p = {
            "call_graph_complete": ["entry"],
            "functions": {
                "entry": {"effects": ["net.send"], "calls": ["unknown"], "effect_bound": []},
            },
        }
        result = check_program(p, "B")
        self.assertIn("EFFECT_BOUND_EXCEEDED", result.codes())
        self.assertIn("EFFECT_SUMMARY_UNKNOWN", result.codes())
        self.assertEqual(result.status, "REJECTED")

    def test_completeness_evidence_rejects_unknown_function_names(self):
        p = {"call_graph_complete": ["ghost"], "functions": {"f": {"effect_bound": []}}}
        with self.assertRaises(ModelError):
            check_program(p, "B")

    def test_rejects_malformed_envelope(self):
        with self.assertRaises(ModelError):
            check_program({"functions": {"f": {}}, "extra": 1}, "A")

if __name__ == "__main__":
    unittest.main()
