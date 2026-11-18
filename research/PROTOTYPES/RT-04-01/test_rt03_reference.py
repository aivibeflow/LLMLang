import unittest

from rt03_reference import SemanticError, evaluate
from rt04_model import check_program


def perform(effect, operation, payload):
    return {"perform": {"effect": effect, "operation": operation, "payload": payload}}


class RT03ReferenceSemanticsTests(unittest.TestCase):
    def test_result_sequence_does_not_change_ordinary_sequence(self):
        trace = evaluate({"sequence": [
            {"result_error": {"literal": {"kind": "Expected"}}},
            {"result_ok": {"literal": 7}},
        ]}, "A")
        self.assertEqual(trace.result, {"ok": 7})

    def test_profile_a_evaluates_strict_pure_arithmetic(self):
        trace = evaluate(
            {"add": [{"literal": 19}, {"add": [{"literal": 20}, {"literal": 3}]}]},
            "A",
        )
        self.assertEqual(trace.result, 42)
        self.assertEqual(trace.events, ())
        self.assertEqual(trace.final_state, {})
        self.assertEqual(trace.final_files, {})

    def test_profile_a_preserves_explicit_error_as_a_value(self):
        trace = evaluate({"result_error": {"literal": {"kind": "InvalidInput"}}}, "A")
        self.assertEqual(trace.result, {"error": {"kind": "InvalidInput"}})
        self.assertEqual(trace.events, ())

    def test_result_sequence_propagates_first_error_and_skips_later_effects(self):
        expression = {"result_sequence": [
            {"result_ok": {"literal": 1}},
            {"result_error": {"literal": {"kind": "InvalidInput"}}},
            perform("state.write", "write", {"key": "must_not_exist", "value": True}),
        ]}
        trace = evaluate(expression, "D", declared_effects=["state.write"])
        self.assertEqual(trace.result, {"error": {"kind": "InvalidInput"}})
        self.assertEqual(trace.events, ())
        self.assertEqual(trace.final_state, {})

    def test_result_sequence_returns_last_success(self):
        trace = evaluate({"result_sequence": [
            {"result_ok": {"literal": 1}},
            {"result_ok": {"literal": 2}},
        ]}, "A")
        self.assertEqual(trace.result, {"ok": 2})

    def test_result_sequence_rejects_non_result_item(self):
        with self.assertRaisesRegex(SemanticError, "Result-shaped"):
            evaluate({"result_sequence": [{"literal": 1}]}, "A")

    def test_profile_a_rejects_effectful_expression(self):
        with self.assertRaisesRegex(SemanticError, "Profile A is pure"):
            evaluate(perform("fs.read", "read", {"path": "/cfg"}), "A",
                     declared_effects=["fs.read"], files={"/cfg": "ok"})

    def test_profile_d_requires_effect_declaration(self):
        with self.assertRaisesRegex(SemanticError, "is not declared"):
            evaluate(perform("fs.read", "read", {"path": "/cfg"}), "D")

    def test_profile_d_reads_file_and_records_request_and_outcome(self):
        trace = evaluate(
            perform("fs.read", "read", {"path": "/cfg"}),
            "D",
            declared_effects=["fs.read"],
            files={"/cfg": "contents"},
        )
        self.assertEqual(trace.result, {"ok": "contents"})
        self.assertEqual(trace.events, ({
            "effect": "fs.read",
            "operation": "read",
            "payload": {"path": "/cfg"},
            "outcome": {"ok": "contents"},
        },))

    def test_profile_d_records_missing_file_as_explicit_error_outcome(self):
        trace = evaluate(
            perform("fs.read", "read", {"path": "/missing"}),
            "D",
            declared_effects=["fs.read"],
        )
        self.assertEqual(trace.result, {"error": {"kind": "NotFound", "path": "/missing"}})
        self.assertEqual(len(trace.events), 1)
        self.assertEqual(trace.events[0]["outcome"], trace.result)

    def test_profile_d_preserves_order_and_state_transition_values(self):
        expression = {"sequence": [
            perform("state.write", "write", {"key": "counter", "value": 1}),
            perform("state.read", "read", {"key": "counter"}),
            perform("state.write", "write", {"key": "counter", "value": 2}),
            perform("state.read", "read", {"key": "counter"}),
        ]}
        trace = evaluate(expression, "D", declared_effects=["state.read", "state.write"])
        self.assertEqual([event["effect"] for event in trace.events], [
            "state.write", "state.read", "state.write", "state.read"
        ])
        self.assertEqual([event["payload"].get("value") for event in trace.events if "value" in event["payload"]], [1, 2])
        self.assertEqual(trace.result, {"ok": 2})
        self.assertEqual(trace.final_state, {"counter": 2})

    def test_reordering_writes_changes_observable_trace_and_final_state(self):
        first = {"sequence": [
            perform("state.write", "write", {"key": "x", "value": 1}),
            perform("state.write", "write", {"key": "x", "value": 2}),
            perform("state.read", "read", {"key": "x"}),
        ]}
        second = {"sequence": [
            perform("state.write", "write", {"key": "x", "value": 2}),
            perform("state.write", "write", {"key": "x", "value": 1}),
            perform("state.read", "read", {"key": "x"}),
        ]}
        a = evaluate(first, "D", declared_effects=["state.read", "state.write"])
        b = evaluate(second, "D", declared_effects=["state.read", "state.write"])
        self.assertNotEqual(a.events, b.events)
        self.assertEqual(a.result, {"ok": 2})
        self.assertEqual(b.result, {"ok": 1})

    def test_rt04_effect_summary_does_not_represent_ordered_runtime_trace(self):
        expression = {"sequence": [
            perform("state.write", "write", {"key": "x", "value": 1}),
            perform("state.read", "read", {"key": "x"}),
            perform("state.write", "write", {"key": "x", "value": 2}),
        ]}
        trace = evaluate(expression, "D", declared_effects=["state.read", "state.write"])
        checked = check_program({
            "functions": {"entry": {"effects": ["state.write", "state.read"], "effect_row": "e"}}
        }, "B")
        self.assertEqual(checked.status, "ACCEPTED")
        self.assertEqual(dict(checked.inferred_effects)["entry"], ("state.read", "state.write"))
        self.assertEqual([event["effect"] for event in trace.events], [
            "state.write", "state.read", "state.write"
        ])
        # The checker reports a set-like summary; the reference semantics retains
        # repeated occurrences, order, operation, payload, and handler outcome.

    def test_net_send_uses_deterministic_fixture_response(self):
        trace = evaluate(
            perform("net.send", "send", {"endpoint": "svc", "message": {"ping": 1}}),
            "D",
            declared_effects=["net.send"],
            network_responses={"svc": {"pong": 1}},
        )
        self.assertEqual(trace.result, {"ok": {"pong": 1}})
        self.assertEqual(trace.events[0]["payload"], {"endpoint": "svc", "message": {"ping": 1}})

    def test_unsupported_handler_fails_closed(self):
        with self.assertRaisesRegex(SemanticError, "no reference handler"):
            evaluate(perform("clock.read", "now", {}), "D", declared_effects=["clock.read"])

    def test_initial_inputs_are_not_mutated(self):
        state = {"n": 0}
        files = {"/f": "old"}
        evaluate(
            {"sequence": [
                perform("state.write", "write", {"key": "n", "value": 1}),
                perform("fs.write", "write", {"path": "/f", "value": "new"}),
            ]},
            "D",
            declared_effects=["state.write", "fs.write"],
            initial_state=state,
            files=files,
        )
        self.assertEqual(state, {"n": 0})
        self.assertEqual(files, {"/f": "old"})

    def test_malformed_expression_fails_closed(self):
        with self.assertRaises(SemanticError):
            evaluate({"add": [{"literal": 1}]}, "A")


if __name__ == "__main__":
    unittest.main()
