import unittest
from itertools import product

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


def _condition_markers(expression):
    """Map each direct unknown_bool condition to its path-model AST path."""
    found = {}

    def visit(node, path="$", inside_condition=False):
        op, arg = next(iter(node.items()))
        if op == "unknown_bool":
            if not inside_condition:
                raise AssertionError("unknown_bool is only supported as an if condition")
            if path in found or arg in found.values():
                raise AssertionError("condition markers and paths must be unique")
            found[path] = arg
        elif op == "if":
            condition = arg["condition"]
            if isinstance(condition, dict) and set(condition) == {"unknown_bool"}:
                marker = condition["unknown_bool"]
                if path in found or marker in found.values():
                    raise AssertionError("condition markers and paths must be unique")
                found[path] = marker
            else:
                visit(condition, f"{path}.condition")
            visit(arg["then"], f"{path}.then")
            visit(arg["else"], f"{path}.else")
        elif op == "with_resource":
            visit(arg["body"], f"{path}.body")
        elif op in {"result_ok", "result_error"}:
            visit(arg, f"{path}.{op}")
        elif op in {"sequence", "result_sequence"}:
            for index, item in enumerate(arg):
                visit(item, f"{path}.{op}[{index}]")
        elif op == "add":
            for index, item in enumerate(arg):
                visit(item, f"{path}.add[{index}]")
        elif op in {"literal", "cancel"}:
            return
        else:
            raise AssertionError(f"unsupported coverage-audit form: {op}")

    visit(expression)
    return found


def _materialize_conditions(expression, assignments):
    """Replace every unknown_bool marker with its concrete Boolean input."""
    op, arg = next(iter(expression.items()))
    if op == "unknown_bool":
        return {"literal": assignments[arg]}
    if op == "if":
        return {"if": {
            "condition": _materialize_conditions(arg["condition"], assignments),
            "then": _materialize_conditions(arg["then"], assignments),
            "else": _materialize_conditions(arg["else"], assignments),
        }}
    if op == "with_resource":
        return {"with_resource": {
            **{key: value for key, value in arg.items() if key != "body"},
            "body": _materialize_conditions(arg["body"], assignments),
        }}
    if op in {"result_ok", "result_error"}:
        return {op: _materialize_conditions(arg, assignments)}
    if op in {"sequence", "result_sequence", "add"}:
        return {op: [_materialize_conditions(item, assignments) for item in arg]}
    return expression


def _path_observation(resource_trace, final_resources, result):
    terminal = "cancelled" if isinstance(result, dict) and "cancelled" in result else "normal"
    result_tag = None
    if isinstance(result, dict) and len(result) == 1 and next(iter(result)) in {"ok", "error"}:
        result_tag = next(iter(result))
    cleanup_errors = tuple(
        resource_id for action, resource_id, succeeded in resource_trace
        if action == "release" and not succeeded
    )
    return (
        resource_trace,
        tuple(sorted(final_resources)),
        terminal,
        result_tag,
        cleanup_errors,
    )


def _fully_branched_tree(depth, prefix="", leaf_counter=None):
    """Build a full binary tree with unique resource witnesses at its leaves."""
    if leaf_counter is None:
        leaf_counter = [0]
    if depth == 0:
        index = leaf_counter[0]
        leaf_counter[0] += 1
        outcomes = (
            {"literal": index},
            {"result_error": {"literal": f"error-{index}"}},
            {"cancel": f"cancel-{index}"},
            {"result_ok": {"literal": index}},
        )
        return {"with_resource": {
            "id": f"leaf-{index}",
            "value": f"value-{index}",
            "release_fails": index % 3 == 1,
            "body": outcomes[index % len(outcomes)],
        }}
    marker = f"choice-{prefix or 'root'}"
    return {"if": {
        "condition": {"unknown_bool": marker},
        "then": _fully_branched_tree(depth - 1, prefix + "t", leaf_counter),
        "else": _fully_branched_tree(depth - 1, prefix + "f", leaf_counter),
    }}


class RT03IndependentPathModelTests(unittest.TestCase):
    def assert_model_matches_both_evaluators(self, expression):
        paths = enumerate_paths(expression)
        self.assertEqual(len(paths), 1, "concrete fixture should have exactly one path")
        path = paths[0]
        recursive = evaluate(expression, "D")
        machine = run_small_step(expression, "D")
        for trace in (recursive, machine):
            self.assertEqual(resource_events(trace), path.resource_events)
            self.assertEqual(tuple(sorted(trace.final_resources)), path.active_resources)
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

    def test_exhaustive_two_resource_branch_cleanup_matrix(self):
        # Exhaust all combinations in this finite matrix:
        # 2 branch values × 2 outer release outcomes × 2 inner release outcomes
        # × 3 selected body outcomes × 3 unselected body outcomes = 72 cases.
        outcomes = {
            "normal": {"literal": "completed"},
            "result_error": {"result_error": {"literal": {"kind": "BodyFailed"}}},
            "cancel": {"cancel": {"kind": "BodyCancelled"}},
        }
        cases = 0
        for condition, outer_fails, inner_fails, selected_kind, skipped_kind in product(
            (True, False), (False, True), (False, True),
            tuple(outcomes), tuple(outcomes),
        ):
            expression = {"with_resource": {
                "id": "outer", "value": "outer-handle",
                "release_fails": outer_fails,
                "body": {"with_resource": {
                    "id": "inner", "value": "inner-handle",
                    "release_fails": inner_fails,
                    "body": {"if": {
                        "condition": {"literal": condition},
                        "then": outcomes[selected_kind],
                        "else": outcomes[skipped_kind],
                    }},
                }},
            }}
            with self.subTest(
                condition=condition, outer_release_fails=outer_fails,
                inner_release_fails=inner_fails, selected=selected_kind,
                skipped=skipped_kind,
            ):
                self.assert_model_matches_both_evaluators(expression)
            cases += 1
        self.assertEqual(cases, 72)

    def test_unknown_condition_enumerates_both_branches_independently(self):
        expression = {"with_resource": {
            "id": "outer", "value": "handle",
            "body": {"if": {
                "condition": {"unknown_bool": "first-condition"},
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
            "condition": {"unknown_bool": "outer-condition"},
            "then": {"if": {
                "condition": {"unknown_bool": "inner-condition"},
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

    def test_exhaustive_ast_condition_valuations_cover_every_structural_path(self):
        # Seven distinct unknown conditions produce 128 concrete input maps;
        # the abstract path model must produce exactly the eight feasible leaves.
        tree = {"with_resource": {
            "id": "root",
            "value": "root-value",
            "release_fails": True,
            "body": _fully_branched_tree(3),
        }}
        marker_paths = _condition_markers(tree)
        self.assertEqual(len(marker_paths), 7)
        markers = tuple(marker_paths.values())
        paths = enumerate_paths(tree)
        self.assertEqual(len(paths), 8)
        observed_paths = {
            (
                path.resource_events, path.active_resources, path.terminal,
                path.result_tag, path.cleanup_errors,
            )
            for path in paths
        }
        self.assertEqual(len(observed_paths), len(paths), "each feasible path has a distinct resource witness")

        path_model_conditions = {
            path for outcome in paths for path, _ in outcome.branch_choices
        }
        self.assertEqual(path_model_conditions, set(marker_paths))

        concrete_observations = set()
        assignments_checked = 0
        for values in product((False, True), repeat=len(markers)):
            assignment = dict(zip(markers, values))
            concrete = _materialize_conditions(tree, assignment)
            recursive = evaluate(concrete, "D")
            machine = run_small_step(concrete, "D")
            recursive_resources = resource_events(recursive)
            machine_resources = resource_events(machine)
            self.assertEqual(recursive.events, machine.events)
            self.assertEqual(recursive.final_resources, machine.final_resources)
            recursive_observation = _path_observation(
                recursive_resources, recursive.final_resources, recursive.result,
            )
            machine_observation = _path_observation(
                machine_resources, machine.final_resources, machine.result,
            )
            self.assertEqual(recursive_observation, machine_observation)
            concrete_observations.add(recursive_observation)
            assignments_checked += 1
        self.assertEqual(assignments_checked, 128)
        self.assertEqual(concrete_observations, observed_paths)

        # Also construct one concrete witness directly from each abstract path.
        for path in paths:
            by_marker = {
                marker_paths[path_id]: choice
                for path_id, choice in path.branch_choices
            }
            assignment = {marker: by_marker.get(marker, False) for marker in markers}
            concrete = _materialize_conditions(tree, assignment)
            trace = evaluate(concrete, "D")
            self.assertEqual(
                _path_observation(resource_events(trace), trace.final_resources, trace.result),
                (
                    path.resource_events, path.active_resources, path.terminal,
                    path.result_tag, path.cleanup_errors,
                ),
            )

    def test_nested_failed_releases_unwind_all_scopes_and_remain_active(self):
        expression = {"with_resource": {
            "id": "outer", "value": 1, "release_fails": True,
            "body": {"with_resource": {
                "id": "inner", "value": 2, "release_fails": True,
                "body": {"cancel": "stop"},
            }},
        }}
        path = self.assert_model_matches_both_evaluators(expression)
        self.assertEqual(path.resource_events, (
            ("acquire", "outer", True), ("acquire", "inner", True),
            ("release", "inner", False), ("release", "outer", False),
        ))
        self.assertEqual(path.active_resources, ("inner", "outer"))
        self.assertEqual(path.cleanup_errors, ("inner", "outer"))

    def test_cancellation_while_evaluating_condition_does_not_invent_branch(self):
        expression = {"with_resource": {
            "id": "outer", "value": "handle",
            "body": {"if": {
                "condition": {"cancel": "condition-cancelled"},
                "then": {"literal": "unreachable"},
                "else": {"literal": "unreachable"},
            }},
        }}
        paths = enumerate_paths(expression)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0].branch_choices, ())
        self.assertEqual(paths[0].terminal, "cancelled")
        self.assertEqual(paths[0].resource_events, (
            ("acquire", "outer", True), ("release", "outer", True),
        ))

    def test_literal_non_boolean_condition_is_rejected_by_path_model(self):
        expression = {"if": {
            "condition": {"literal": 7},
            "then": {"literal": "then"},
            "else": {"literal": "else"},
        }}
        with self.assertRaisesRegex(ValueError, "condition must be boolean"):
            enumerate_paths(expression)

    def test_cancellation_inside_add_operand_unwinds_enclosing_resource(self):
        expression = {"with_resource": {
            "id": "outer", "value": "handle",
            "body": {"add": [
                {"literal": 1},
                {"cancel": "cancelled-in-right-operand"},
            ]},
        }}
        path = self.assert_model_matches_both_evaluators(expression)
        self.assertEqual(path.terminal, "cancelled")
        self.assertEqual(path.resource_events, (
            ("acquire", "outer", True), ("release", "outer", True),
        ))

    def test_result_wrappers_override_inner_result_tag_but_preserve_cancellation(self):
        ok_wrapped_error = {"result_ok": {"result_error": {"literal": "inner"}}}
        error_wrapped_ok = {"result_error": {"result_ok": {"literal": "inner"}}}
        cancelled = {"result_ok": {"cancel": "stop"}}
        self.assertEqual(enumerate_paths(ok_wrapped_error)[0].result_tag, "ok")
        self.assertEqual(enumerate_paths(error_wrapped_ok)[0].result_tag, "error")
        cancelled_path = enumerate_paths(cancelled)[0]
        self.assertEqual(cancelled_path.terminal, "cancelled")
        self.assertIsNone(cancelled_path.result_tag)

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
