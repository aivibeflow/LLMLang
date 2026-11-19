import unittest

from rt03_path_model import enumerate_paths
from rt03_predicate_paths import enumerate_feasible_paths
from rt03_sympy_predicate_paths import enumerate_solver_paths
from rt03_reference import evaluate
from rt03_smallstep import run_small_step
from test_rt03_path_model import _path_observation, resource_events
from test_rt03_predicate_paths import _materialize


def _resource(resource_id):
    return {"with_resource": {
        "id": resource_id,
        "value": resource_id,
        "body": {"literal": "done"},
    }}


def _fixture():
    return {"sequence": [
        {"if": {
            "condition": {"bool_var": "x"},
            "then": _resource("x-true"),
            "else": _resource("x-false"),
        }},
        {"if": {
            "condition": {"bool_or": [{"bool_var": "x"}, {"bool_var": "y"}]},
            "then": _resource("x-or-y-true"),
            "else": _resource("x-or-y-false"),
        }},
    ]}


class SympyPredicatePathTests(unittest.TestCase):
    def test_dpll_routes_equal_truth_table_and_concrete_evaluators(self):
        expression = _fixture()
        truth_table = enumerate_feasible_paths(expression)
        solver = enumerate_solver_paths(expression)
        by_choices = {path.branch_choices: dict(path.witness) for path in solver}
        truth_table_choices = {path.branch_choices for path in truth_table}
        self.assertEqual(set(by_choices), truth_table_choices)
        self.assertEqual(
            {tuple(choice for _, choice in choices) for choices in by_choices},
            {(True, True), (False, True), (False, False)},
        )

        for choices, witness in by_choices.items():
            concrete = _materialize(expression, witness)
            path = enumerate_paths(concrete)[0]
            recursive = evaluate(concrete, "D")
            machine = run_small_step(concrete, "D")
            self.assertEqual(path.branch_choices, choices)
            self.assertEqual(recursive.events, machine.events)
            self.assertEqual(recursive.final_resources, machine.final_resources)
            self.assertEqual(
                _path_observation(resource_events(recursive), recursive.final_resources, recursive.result),
                (
                    path.resource_events, path.active_resources, path.terminal,
                    path.result_tag, path.cleanup_errors,
                ),
            )

    def test_dpll_drops_contradictory_branch_and_returns_replayable_witness(self):
        expression = {"if": {
            "condition": {"bool_and": [
                {"bool_or": [{"bool_var": "x"}, {"bool_var": "y"}]},
                {"bool_and": [
                    {"bool_not": {"bool_var": "x"}},
                    {"bool_not": {"bool_var": "y"}},
                ]},
            ]},
            "then": {"literal": "unreachable"},
            "else": {"literal": "reachable"},
        }}
        paths = enumerate_solver_paths(expression)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0].branch_choices[0][1], False)
        concrete = _materialize(expression, dict(paths[0].witness))
        self.assertFalse(concrete["if"]["condition"]["literal"])
        self.assertEqual(enumerate_paths(concrete)[0].branch_choices, paths[0].branch_choices)


if __name__ == "__main__":
    unittest.main()
