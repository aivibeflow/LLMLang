import random
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


def _generated_predicate(rng, depth):
    variables = ("x0", "x1", "x2", "x3", "x4", "x5")
    if depth == 0 or rng.random() < 0.22:
        return {"bool_var": rng.choice(variables)}
    op = rng.choice(("bool_not", "bool_and", "bool_or"))
    if op == "bool_not":
        return {op: _generated_predicate(rng, depth - 1)}
    return {
        op: [
            _generated_predicate(rng, depth - 1),
            _generated_predicate(rng, depth - 1),
        ]
    }


def _evaluate_predicate(predicate, assignment):
    op, arg = next(iter(predicate.items()))
    if op == "bool_var":
        return assignment[arg]
    if op == "bool_not":
        return not _evaluate_predicate(arg, assignment)
    left, right = arg
    if op == "bool_and":
        return _evaluate_predicate(left, assignment) and _evaluate_predicate(right, assignment)
    return _evaluate_predicate(left, assignment) or _evaluate_predicate(right, assignment)


class SympyPredicatePathTests(unittest.TestCase):
    def test_generated_predicates_match_truth_table_and_replay_models(self):
        rng = random.Random(102)
        for case in range(128):
            with self.subTest(case=case):
                predicate = _generated_predicate(rng, depth=4)
                expression = {"if": {
                    "condition": predicate,
                    "then": {"literal": "then"},
                    "else": {"literal": "else"},
                }}
                exact = {
                    path.branch_choices for path in enumerate_feasible_paths(expression)
                }
                solver_paths = enumerate_solver_paths(expression)
                actual = {path.branch_choices for path in solver_paths}
                self.assertEqual(actual, exact)
                for path in solver_paths:
                    self.assertEqual(
                        _evaluate_predicate(predicate, dict(path.witness)),
                        path.branch_choices[0][1],
                    )

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
