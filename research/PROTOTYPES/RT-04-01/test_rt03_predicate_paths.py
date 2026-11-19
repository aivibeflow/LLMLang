import itertools
import unittest

from rt03_path_model import enumerate_paths
from rt03_predicate_paths import enumerate_feasible_paths
from rt03_reference import evaluate
from rt03_smallstep import run_small_step
from test_rt03_path_model import _path_observation, resource_events


def _resource(resource_id):
    return {"with_resource": {
        "id": resource_id,
        "value": resource_id,
        "body": {"literal": "done"},
    }}


def _materialize(expression, assignment):
    op, arg = next(iter(expression.items()))
    if op == "if":
        return {"if": {
            "condition": {"literal": _eval_predicate(arg["condition"], assignment)},
            "then": _materialize(arg["then"], assignment),
            "else": _materialize(arg["else"], assignment),
        }}
    if op == "sequence":
        return {op: [_materialize(item, assignment) for item in arg]}
    if op == "with_resource":
        return {op: {
            **{key: value for key, value in arg.items() if key != "body"},
            "body": _materialize(arg["body"], assignment),
        }}
    return expression


def _eval_predicate(predicate, assignment):
    op, arg = next(iter(predicate.items()))
    if op == "literal":
        return arg
    if op == "bool_var":
        return assignment[arg]
    if op == "bool_not":
        return not _eval_predicate(arg, assignment)
    if op == "bool_and":
        return _eval_predicate(arg[0], assignment) and _eval_predicate(arg[1], assignment)
    if op == "bool_or":
        return _eval_predicate(arg[0], assignment) or _eval_predicate(arg[1], assignment)
    raise AssertionError(f"unexpected predicate {op!r}")


class FinitePredicatePathTests(unittest.TestCase):
    def test_exhaustive_boolean_predicate_paths_match_concrete_evaluators(self):
        expression = {"sequence": [
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

        feasible = enumerate_feasible_paths(expression)
        by_choices = {path.branch_choices: dict(path.witness) for path in feasible}
        choice_vectors = {tuple(choice for _, choice in choices) for choices in by_choices}
        self.assertEqual(choice_vectors, {(True, True), (False, True), (False, False)})
        self.assertNotIn((True, False), choice_vectors)

        concrete_assignments = tuple(itertools.product((False, True), repeat=2))
        observed_choices = set()
        for values in concrete_assignments:
            assignment = dict(zip(("x", "y"), values))
            concrete = _materialize(expression, assignment)
            path = enumerate_paths(concrete)[0]
            recursive = evaluate(concrete, "D")
            machine = run_small_step(concrete, "D")
            self.assertEqual(recursive.events, machine.events)
            self.assertEqual(recursive.final_resources, machine.final_resources)
            self.assertEqual(
                _path_observation(resource_events(recursive), recursive.final_resources, recursive.result),
                (
                    path.resource_events, path.active_resources, path.terminal,
                    path.result_tag, path.cleanup_errors,
                ),
            )
            observed_choices.add(path.branch_choices)
            self.assertIn(path.branch_choices, by_choices)

        self.assertEqual(observed_choices, set(by_choices))
        for choices, witness in by_choices.items():
            concrete = _materialize(expression, witness)
            self.assertEqual(enumerate_paths(concrete)[0].branch_choices, choices)

    def test_boolean_variable_generates_both_assignments(self):
        expression = {"if": {
            "condition": {"bool_var": "x"},
            "then": {"literal": "yes"},
            "else": {"literal": "no"},
        }}
        self.assertEqual(len(enumerate_feasible_paths(expression)), 2)

    def test_unsupported_predicate_fails_closed(self):
        expression = {"if": {
            "condition": {"integer_compare": [1, 2]},
            "then": {"literal": "yes"},
            "else": {"literal": "no"},
        }}
        with self.assertRaisesRegex(ValueError, "unsupported Boolean predicate"):
            enumerate_feasible_paths(expression)


if __name__ == "__main__":
    unittest.main()
