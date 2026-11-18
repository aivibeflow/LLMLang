import unittest

from rt03_path_model import enumerate_paths
from rt03_reference import evaluate
from rt03_smallstep import run_small_step


def resource_events(trace):
    result = []
    for event in trace.events:
        if event["effect"] not in {"resource.acquire", "resource.release"}:
            continue
        result.append((
            "acquire" if event["effect"] == "resource.acquire" else "release",
            event["payload"]["id"],
            "error" not in event["outcome"],
        ))
    return tuple(result)


class RT03IndependentPathModelTests(unittest.TestCase):
    def assert_model_matches_both_evaluators(self, expression):
        paths = enumerate_paths(expression)
        self.assertEqual(len(paths), 1, "concrete fixture should have exactly one path")
        path = paths[0]
        recursive = evaluate(expression, "D")
        machine = run_small_step(expression, "D")
        for trace in (recursive, machine):
            self.assertEqual(resource_events(trace), path.resource_events)
            self.assertEqual(tuple(trace.final_resources), path.active_resources)
            self.assertEqual(
                "cancelled" if isinstance(trace.result, dict) and "cancelled" in trace.result else "normal",
                path.terminal,
            )
            result_tag = next(iter(trace.result)) if (
                isinstance(trace.result, dict) and len(trace.result) == 1
                and next(iter(trace.result)) in {"ok", "error"}
            ) else None
            self.assertEqual(result_tag, path.result_tag)
        self.assertEqual(recursive.events, machine.events)
        self.assertEqual(recursive.final_resources, machine.final_resources)
        return path

    def test_independent_model_matches_success_error_and_cancel_paths(self):
        cases = [
            {"with_resource": {
                "id": "r1", "value": "handle",
                "body": {"literal": "done"},
            }},
            {"with_resource": {
                "id": "r1", "value": "handle",
                "body": {"result_error": {"literal": "failed"}},
            }},
            {"with_resource": {
                "id": "r1", "value": "handle",
                "body": {"cancel": {"kind": "stop"}},
            }},
            {"with_resource": {
                "id": "r1", "value": "handle", "release_fails": True,
                "body": {"cancel": {"kind": "stop"}},
            }},
            {"with_resource": {
                "id": "outer", "value": 1,
                "body": {"with_resource": {
                    "id": "inner", "value": 2,
                    "body": {"cancel": {"kind": "stop"}},
                }},
            }},
            {"with_resource": {
                "id": "outer", "value": 1, "release_fails": True,
                "body": {"with_resource": {
                    "id": "inner", "value": 2, "release_fails": True,
                    "body": {"cancel": {"kind": "stop"}},
                }},
            }},
            {"with_resource": {
                "id": "r1", "value": "handle",
                "body": {"if": {
                    "condition": {"literal": True},
                    "then": {"result_error": {"literal": "branch-error"}},
                    "else": {"cancel": "unselected"},
                }},
            }},
            {"with_resource": {
                "id": "r1", "value": "handle",
                "body": {"if": {
                    "condition": {"literal": False},
                    "then": {"cancel": "unselected"},
                    "else": {"cancel": "selected"},
                }},
            }},
            {"with_resource": {
                "id": "r1", "value": "handle",
                "body": {"result_sequence": [
                    {"result_ok": {"literal": 1}},
                    {"result_error": {"literal": "stop"}},
                    {"cancel": "must-not-run"},
                ]},
            }},
        ]
        for expression in cases:
            with self.subTest(expression=expression):
                self.assert_model_matches_both_evaluators(expression)

    def test_unknown_condition_enumerates_both_branches_independently(self):
        expression = {"with_resource": {
            "id": "outer", "value": "handle",
            "body": {"if": {
                "condition": {"perform": {
                    "effect": "abstract.bool", "operation": "read", "payload": {},
                }},
                "then": {"result_error": {"literal": "then-error"}},
                "else": {"cancel": "else-cancel"},
            }},
        }}
        paths = enumerate_paths(expression)
        self.assertEqual(len(paths), 2)
        self.assertEqual({choices[-1][1] for choices in (p.branch_choices for p in paths)}, {True, False})
        self.assertTrue(all(p.resource_events == (
            ("acquire", "outer", True), ("release", "outer", True)
        ) for p in paths))
        self.assertTrue(all(not p.active_resources for p in paths))
        self.assertEqual({p.terminal for p in paths}, {"normal", "cancelled"})
        self.assertEqual({p.result_tag for p in paths}, {"error", None})

    def test_nested_conditionals_enumerate_cartesian_path_set(self):
        expression = {"if": {
            "condition": {"perform": {"effect": "abstract.bool", "operation": "read", "payload": {}}},
            "then": {"if": {
                "condition": {"perform": {"effect": "abstract.bool", "operation": "read", "payload": {}}},
                "then": {"literal": "tt"},
                "else": {"literal": "tf"},
            }},
            "else": {"literal": "f"},
        }}
        paths = enumerate_paths(expression)
        self.assertEqual(len(paths), 3)
        self.assertEqual(
            {tuple(choice for _, choice in path.branch_choices) for path in paths},
            {(True, True), (True, False), (False,)},
        )

    def test_result_error_does_not_short_circuit_ordinary_sequence(self):
        expression = {"sequence": [
            {"result_error": {"literal": "ordinary-value"}},
            {"literal": "later-expression-ran"},
        ]}
        paths = enumerate_paths(expression)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0].result_tag, None)

    def test_result_sequence_error_short_circuits_path_enumeration(self):
        expression = {"result_sequence": [
            {"result_error": {"literal": "stop"}},
            {"cancel": "must-not-run"},
        ]}
        paths = enumerate_paths(expression)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0].terminal, "normal")
        self.assertEqual(paths[0].result_tag, "error")


if __name__ == "__main__":
    unittest.main()
