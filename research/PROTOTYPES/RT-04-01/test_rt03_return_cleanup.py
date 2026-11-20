import unittest

from rt03_path_model import enumerate_paths
from rt03_reference import evaluate
from rt03_return_cleanup import Event, Observation, run_return_cleanup


class ReturnCleanupProjection(unittest.TestCase):
    def test_reserve_commit_cleans_pending_value_when_local_cleanup_fails(self):
        trace = run_return_cleanup("reserve_then_commit", temporary_release_fails=True)
        self.assertEqual(trace.outcome, "error")
        self.assertIsNone(trace.returned)
        self.assertEqual(trace.events[-2:], (
            Event("release", "temporary", "error"),
            Event("release", "handle", "ok"),
        ))
        self.assertEqual(trace.owners, (("temporary", "callee_cleanup_debt"),))

    def test_failed_pending_value_cleanup_is_retained_as_explicit_debt(self):
        trace = run_return_cleanup(
            "reserve_then_commit", temporary_release_fails=True, handle_release_fails=True,
        )
        self.assertEqual(trace.outcome, "error")
        self.assertEqual(dict(trace.owners), {
            "handle": "pending_return_cleanup_debt",
            "temporary": "callee_cleanup_debt",
        })

    def test_transfer_before_cleanup_requires_error_with_value_on_local_failure(self):
        trace = run_return_cleanup("transfer_then_cleanup", temporary_release_fails=True)
        self.assertEqual(trace.outcome, "error_with_value")
        self.assertEqual(trace.returned, "handle")
        self.assertEqual(dict(trace.owners), {
            "handle": "caller", "temporary": "callee_cleanup_debt",
        })

    def test_transferred_handle_is_released_once_by_caller(self):
        trace = run_return_cleanup(
            "transfer_then_cleanup", caller_exits_after_return=True,
        )
        releases = [event for event in trace.events if event.operation == "release"]
        self.assertEqual(releases, [Event("release", "temporary", "ok"),
                                    Event("release", "handle", "ok")])
        self.assertEqual(trace.owners, ())

    def test_caller_can_release_value_from_error_with_value_before_propagating_error(self):
        trace = run_return_cleanup(
            "transfer_then_cleanup", temporary_release_fails=True,
            caller_exits_after_return=True,
        )
        self.assertEqual(trace.outcome, "error_with_value")
        self.assertEqual(trace.returned, "handle")
        self.assertEqual(trace.events[-2:], (
            Event("release", "temporary", "error"),
            Event("release", "handle", "ok"),
        ))
        self.assertEqual(trace.owners, (("temporary", "callee_cleanup_debt"),))

    def test_local_borrow_and_implicit_escape_are_static_rejections(self):
        for policy in ("reject_escape", "borrow_only"):
            with self.subTest(policy=policy):
                self.assertEqual(run_return_cleanup(policy),
                                 Observation("static_reject", None, (), ()))

    def test_bad_inputs_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            run_return_cleanup("unknown")
        with self.assertRaisesRegex(ValueError, "booleans"):
            run_return_cleanup("reserve_then_commit", temporary_release_fails=1)

    def test_local_cleanup_projection_matches_existing_evaluator_and_path_model(self):
        for policy in ("reserve_then_commit", "transfer_then_cleanup"):
            for release_fails in (False, True):
                with self.subTest(policy=policy, release_fails=release_fails):
                    projection = run_return_cleanup(
                        policy, temporary_release_fails=release_fails,
                    )
                    expression = {"with_resource": {
                        "id": "temporary", "value": "temp",
                        "release_fails": release_fails,
                        "body": {"literal": "body"},
                    }}
                    reference = evaluate(expression, "D")
                    paths = enumerate_paths(expression)
                    self.assertEqual(len(paths), 1)
                    path = paths[0]

                    ref_cleanup = tuple(
                        Event(
                            "release", event["payload"]["id"],
                            "error" if "error" in event["outcome"] else "ok",
                        )
                        for event in reference.events
                        if event["effect"] == "resource.release"
                    )
                    path_cleanup = tuple(
                        Event("release", resource, "ok" if succeeded else "error")
                        for operation, resource, succeeded in path.resource_events
                        if operation == "release"
                    )
                    projected_local_cleanup = tuple(
                        event for event in projection.events
                        if event.operation == "release" and event.resource == "temporary"
                    )
                    self.assertEqual(ref_cleanup, (Event(
                        "release", "temporary", "error" if release_fails else "ok",
                    ),))
                    self.assertEqual(path_cleanup, ref_cleanup)
                    self.assertEqual(projected_local_cleanup, ref_cleanup)
                    self.assertEqual(
                        "temporary" in reference.final_resources,
                        release_fails,
                    )
                    self.assertEqual(path.active_resources, ("temporary",) if release_fails else ())
                    self.assertEqual(
                        ("temporary", "callee_cleanup_debt") in projection.owners,
                        release_fails,
                    )

    def test_error_branch_keeps_ownership_local_and_matches_nested_cleanup_models(self):
        for policy in ("reserve_then_commit", "transfer_then_cleanup", "reject_escape", "borrow_only"):
            for temporary_fails in (False, True):
                for handle_fails in (False, True):
                    with self.subTest(policy=policy, temporary_fails=temporary_fails,
                                      handle_fails=handle_fails):
                        projection = run_return_cleanup(
                            policy, body="return_error",
                            temporary_release_fails=temporary_fails,
                            handle_release_fails=handle_fails,
                        )
                        expression = {"with_resource": {
                            "id": "temporary", "value": "temp",
                            "release_fails": temporary_fails,
                            "body": {"with_resource": {
                                "id": "handle", "value": "owned-handle",
                                "release_fails": handle_fails,
                                "body": {"result_error": {"literal": "branch-error"}},
                            }},
                        }}
                        reference = evaluate(expression, "D")
                        paths = enumerate_paths(expression)
                        self.assertEqual(len(paths), 1)
                        path = paths[0]

                        expected_cleanup = (
                            Event("release", "handle", "error" if handle_fails else "ok"),
                            Event("release", "temporary", "error" if temporary_fails else "ok"),
                        )
                        ref_cleanup = tuple(
                            Event(
                                "release", event["payload"]["id"],
                                "error" if "error" in event["outcome"] else "ok",
                            )
                            for event in reference.events
                            if event["effect"] == "resource.release"
                        )
                        path_cleanup = tuple(
                            Event("release", resource, "ok" if succeeded else "error")
                            for operation, resource, succeeded in path.resource_events
                            if operation == "release"
                        )
                        projected_cleanup = tuple(
                            event for event in projection.events
                            if event.operation == "release"
                        )
                        self.assertEqual(ref_cleanup, expected_cleanup)
                        self.assertEqual(path_cleanup, expected_cleanup)
                        self.assertEqual(projected_cleanup, expected_cleanup)
                        self.assertEqual(reference.final_resources.keys(),
                                         set(path.active_resources))
                        self.assertEqual(set(dict(projection.owners)),
                                         set(reference.final_resources))
                        self.assertEqual(projection.outcome, "error")
                        self.assertIsNone(projection.returned)

    def test_unknown_branch_fork_compares_handle_return_and_error_cleanup_paths(self):
        template = {"with_resource": {
            "id": "temporary", "value": "temp",
            "body": {"if": {
                "condition": {"unknown_bool": "has-handle"},
                "then": {"literal": "handle"},
                "else": {"with_resource": {
                    "id": "handle", "value": "owned-handle",
                    "body": {"result_error": {"literal": "branch-error"}},
                }},
            }},
        }}
        for temporary_fails in (False, True):
            expression = {"with_resource": {
                "id": "temporary", "value": "temp",
                "release_fails": temporary_fails,
                "body": template["with_resource"]["body"],
            }}
            paths = enumerate_paths(expression)
            self.assertEqual(len(paths), 2)
            for condition in (True, False):
                path = next(p for p in paths if p.branch_choices == (("$.body", condition),))
                concrete = {"with_resource": {
                    "id": "temporary", "value": "temp",
                    "release_fails": temporary_fails,
                    "body": {"if": {
                        "condition": {"literal": condition},
                        "then": {"literal": "handle"},
                        "else": {"with_resource": {
                            "id": "handle", "value": "owned-handle",
                            "body": {"result_error": {"literal": "branch-error"}},
                        }},
                    }},
                }}
                reference = evaluate(concrete, "D")
                projection = run_return_cleanup(
                    "transfer_then_cleanup",
                    body="return_handle" if condition else "return_error",
                    temporary_release_fails=temporary_fails,
                )
                ref_cleanup = tuple(
                    Event(
                        "release", event["payload"]["id"],
                        "error" if "error" in event["outcome"] else "ok",
                    )
                    for event in reference.events
                    if event["effect"] == "resource.release"
                )
                path_cleanup = tuple(
                    Event("release", resource, "ok" if succeeded else "error")
                    for operation, resource, succeeded in path.resource_events
                    if operation == "release"
                )
                self.assertEqual(path_cleanup, ref_cleanup)
                if condition:
                    projected_temp = tuple(
                        event for event in projection.events
                        if event.operation == "release" and event.resource == "temporary"
                    )
                    self.assertEqual(projected_temp, (Event(
                        "release", "temporary", "error" if temporary_fails else "ok",
                    ),))
                    if temporary_fails:
                        # Current evaluator cleanup loses the return value;
                        # transfer-first explicitly carries it with the error.
                        self.assertEqual(projection.outcome, "error_with_value")
                        self.assertEqual(reference.result["error"]["kind"], "CleanupFailed")
                    else:
                        self.assertEqual(reference.result, "handle")
                        self.assertEqual(projection.outcome, "ok")
                else:
                    projected_cleanup = tuple(
                        event for event in projection.events if event.operation == "release"
                    )
                    self.assertEqual(projected_cleanup, ref_cleanup)
                    self.assertTrue(all(resource != "handle" or owner != "caller"
                                        for resource, owner in projection.owners))


if __name__ == "__main__":
    unittest.main()
