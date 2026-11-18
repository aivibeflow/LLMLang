import unittest

from rt03_reference import SemanticError, evaluate
from rt03_smallstep import MachineError, run_small_step


def perform(effect, operation, payload):
    return {"perform": {"effect": effect, "operation": operation, "payload": payload}}


class RT03DifferentialSemanticsTests(unittest.TestCase):
    def assert_same_trace(self, expression, profile, **kwargs):
        recursive = evaluate(expression, profile, **kwargs)
        machine = run_small_step(expression, profile, **kwargs)
        self.assertEqual(machine.profile, recursive.profile)
        self.assertEqual(machine.events, recursive.events)
        self.assertEqual(machine.result, recursive.result)
        self.assertEqual(machine.final_state, recursive.final_state)
        self.assertEqual(machine.final_files, recursive.final_files)
        return recursive

    def test_result_propagation_rejects_non_result_item_in_both_models(self):
        expression = {"result_sequence": [{"literal": 1}]}
        with self.assertRaises(SemanticError):
            evaluate(expression, "A")
        with self.assertRaises(MachineError):
            run_small_step(expression, "A")

    def test_result_propagation_matches_error_success_and_short_circuit(self):
        cases = [
            ({"result_sequence": [
                {"result_ok": {"literal": 1}},
                {"result_error": {"literal": {"kind": "InvalidInput"}}},
                perform("state.write", "write", {"key": "not_written", "value": 1}),
            ]}, {"error": {"kind": "InvalidInput"}}),
            ({"result_sequence": [
                {"result_ok": {"literal": 1}},
                {"result_ok": {"literal": 2}},
            ]}, {"ok": 2}),
        ]
        for expression, expected in cases:
            with self.subTest(expression=expression):
                trace = self.assert_same_trace(
                    expression, "D", declared_effects=["state.write"]
                )
                self.assertEqual(trace.result, expected)
                if "error" in expected:
                    self.assertEqual(trace.events, ())
                    self.assertEqual(trace.final_state, {})

    def test_pure_expression_corpus_matches(self):
        corpus = [
            {"literal": None},
            {"literal": {"nested": [1, "x", True]}},
            {"add": [{"literal": 20}, {"add": [{"literal": 10}, {"literal": 12}]}]},
            {"sequence": [{"literal": 1}, {"literal": 2}, {"literal": 3}]},
            {"result_ok": {"literal": 42}},
            {"result_error": {"literal": {"kind": "Nope"}}},
            {"add": [
                {"sequence": [{"literal": 3}, {"literal": 4}]},
                {"result_ok": {"literal": 5}},
            ]},
        ]
        for expression in corpus:
            with self.subTest(expression=expression):
                if "add" in expression and expression["add"][1].get("result_ok") is not None:
                    # This malformed type combination must fail in both models.
                    with self.assertRaises(SemanticError):
                        evaluate(expression, "A")
                    with self.assertRaises(MachineError):
                        run_small_step(expression, "A")
                else:
                    self.assert_same_trace(expression, "A")

    def test_result_propagation_matches_and_skips_following_effect(self):
        expression = {"result_sequence": [
            {"result_ok": {"literal": "started"}},
            {"result_error": {"literal": {"kind": "Cancelled"}}},
            perform("state.write", "write", {"key": "after_error", "value": 1}),
        ]}
        trace = self.assert_same_trace(expression, "D", declared_effects=["state.write"])
        self.assertEqual(trace.result, {"error": {"kind": "Cancelled"}})
        self.assertEqual(trace.events, ())
        self.assertEqual(trace.final_state, {})

    def test_result_propagation_rejects_non_result_values_in_both_models(self):
        expression = {"result_sequence": [{"literal": 1}]}
        with self.assertRaises(SemanticError):
            evaluate(expression, "A")
        with self.assertRaises(MachineError):
            run_small_step(expression, "A")

    def test_ordinary_sequence_still_evaluates_after_result_error(self):
        expression = {"sequence": [
            {"result_error": {"literal": {"kind": "Expected"}}},
            perform("state.write", "write", {"key": "continued", "value": True}),
        ]}
        trace = self.assert_same_trace(expression, "D", declared_effects=["state.write"])
        self.assertEqual(trace.result, {"ok": None})
        self.assertEqual(len(trace.events), 1)
        self.assertEqual(trace.final_state, {"continued": True})

    def test_result_propagation_success_matches(self):
        trace = self.assert_same_trace({"result_sequence": [
            {"result_ok": {"literal": 1}},
            {"result_ok": {"literal": 2}},
            {"result_ok": {"literal": 3}},
        ]}, "A")
        self.assertEqual(trace.result, {"ok": 3})

    def test_ordered_state_effect_corpus_matches(self):
        expression = {"sequence": [
            perform("state.write", "write", {"key": "v", "value": 4}),
            perform("state.read", "read", {"key": "v"}),
            perform("state.write", "write", {"key": "v", "value": 9}),
            perform("state.read", "read", {"key": "v"}),
        ]}
        trace = self.assert_same_trace(
            expression, "D", declared_effects=["state.read", "state.write"],
            initial_state={"seed": "unchanged"},
        )
        self.assertEqual(trace.result, {"ok": 9})
        self.assertEqual(len(trace.events), 4)

    def test_file_effect_corpus_matches(self):
        expression = {"sequence": [
            perform("fs.write", "write", {"path": "/tmp/a", "value": "new"}),
            perform("fs.read", "read", {"path": "/tmp/a"}),
            perform("fs.read", "read", {"path": "/missing"}),
        ]}
        trace = self.assert_same_trace(
            expression, "D", declared_effects=["fs.read", "fs.write"],
            files={"/tmp/a": "old"},
        )
        self.assertEqual(trace.result, {"error": {"kind": "NotFound", "path": "/missing"}})
        self.assertEqual(trace.final_files, {"/tmp/a": "new"})

    def test_network_effect_corpus_matches(self):
        expression = perform("net.send", "send", {
            "endpoint": "echo", "message": {"n": 7}
        })
        self.assert_same_trace(
            expression, "D", declared_effects=["net.send"],
            network_responses={"echo": {"reply": 7}},
        )

    def test_reordered_effects_remain_distinguishable_in_both_models(self):
        left = {"sequence": [
            perform("state.write", "write", {"key": "x", "value": "a"}),
            perform("state.write", "write", {"key": "x", "value": "b"}),
        ]}
        right = {"sequence": [
            perform("state.write", "write", {"key": "x", "value": "b"}),
            perform("state.write", "write", {"key": "x", "value": "a"}),
        ]}
        a = self.assert_same_trace(left, "D", declared_effects=["state.write"])
        b = self.assert_same_trace(right, "D", declared_effects=["state.write"])
        self.assertNotEqual(a.events, b.events)
        self.assertNotEqual(a.final_state, b.final_state)

    def test_generated_short_state_sequences_match(self):
        # A small deterministic generated corpus, independent of the hand-written
        # examples above, explores all two-write combinations over three values.
        for first in range(3):
            for second in range(3):
                expression = {"sequence": [
                    perform("state.write", "write", {"key": "counter", "value": first}),
                    perform("state.read", "read", {"key": "counter"}),
                    perform("state.write", "write", {"key": "counter", "value": second}),
                    perform("state.read", "read", {"key": "counter"}),
                ]}
                with self.subTest(first=first, second=second):
                    trace = self.assert_same_trace(
                        expression, "D",
                        declared_effects=["state.read", "state.write"],
                    )
                    self.assertEqual(trace.result, {"ok": second})

    def test_both_reject_profile_a_effects(self):
        expression = perform("fs.read", "read", {"path": "/a"})
        with self.assertRaises(SemanticError):
            evaluate(expression, "A", declared_effects=["fs.read"])
        with self.assertRaises(MachineError):
            run_small_step(expression, "A", declared_effects=["fs.read"])

    def test_both_reject_undeclared_profile_d_effects(self):
        expression = perform("fs.read", "read", {"path": "/a"})
        with self.assertRaises(SemanticError):
            evaluate(expression, "D")
        with self.assertRaises(MachineError):
            run_small_step(expression, "D")

    def test_both_reject_malformed_add(self):
        expression = {"add": [{"literal": 1}]}
        with self.assertRaises(SemanticError):
            evaluate(expression, "A")
        with self.assertRaises(MachineError):
            run_small_step(expression, "A")


if __name__ == "__main__":
    unittest.main()
