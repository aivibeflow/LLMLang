import unittest
from itertools import product

from rt03_path_model import enumerate_paths
from rt03_reference import evaluate
from rt03_resource_rules import BodyOutcome, ResourceFrame, derive_resource_trace
from rt03_smallstep import run_small_step


def expression_for(frames, body, acquire_fail_at=None):
    if body.kind == "normal":
        node = {"literal": body.payload}
    elif body.kind == "result_error":
        node = {"result_error": {"literal": body.payload}}
    else:
        node = {"cancel": body.payload}
    for index, frame in reversed(tuple(enumerate(frames))):
        node = {"with_resource": {
            "id": frame.resource_id,
            "value": frame.value,
            "release_fails": frame.release_fails,
            "acquire_fails": index == acquire_fail_at,
            "body": node,
        }}
    return node


def path_projection(path):
    return (
        tuple(path.resource_events),
        tuple(path.active_resources),
        path.terminal,
        path.result_tag,
    )


class RT03IndependentResourceRulesTests(unittest.TestCase):
    def assert_rules_match_all_models(self, frames, body, acquire_fail_at=None):
        expression = expression_for(frames, body, acquire_fail_at)
        expected = derive_resource_trace(frames, body, acquire_fail_at=acquire_fail_at)
        recursive = evaluate(expression, "D")
        machine = run_small_step(expression, "D")

        for trace in (recursive, machine):
            self.assertEqual(trace.events, expected.events)
            self.assertEqual(trace.result, expected.result)
            self.assertEqual(trace.final_resources, expected.final_resources)

        path = enumerate_paths(expression)[0]
        expected_events = tuple(
            (
                "acquire" if event["effect"] == "resource.acquire" else "release",
                event["payload"]["id"],
                "error" not in event["outcome"],
            )
            for event in expected.events
        )
        self.assertEqual(path.resource_events, expected_events)
        self.assertEqual(path.active_resources, tuple(sorted(expected.final_resources)))
        self.assertEqual(
            path.terminal,
            "cancelled" if isinstance(expected.result, dict) and "cancelled" in expected.result
            else "normal",
        )
        result_tag = next(iter(expected.result)) if (
            isinstance(expected.result, dict) and len(expected.result) == 1
            and next(iter(expected.result)) in {"ok", "error"}
        ) else None
        self.assertEqual(path.result_tag, result_tag)
        return expected

    def test_exhaustive_depth_one_to_three_outcome_and_acquisition_matrix(self):
        bodies = (
            BodyOutcome("normal", {"completed": True}),
            BodyOutcome("result_error", {"kind": "BodyFailed"}),
            BodyOutcome("cancelled", {"kind": "BodyCancelled"}),
        )
        cases = 0
        for depth in (1, 2, 3):
            ids = tuple(f"r{index}" for index in range(depth))
            for release_flags in product((False, True), repeat=depth):
                frames = tuple(
                    ResourceFrame(resource_id, {"slot": index}, release_flags[index])
                    for index, resource_id in enumerate(ids)
                )
                for body in bodies:
                    for acquire_fail_at in (None, *range(depth)):
                        with self.subTest(
                            depth=depth, release_flags=release_flags,
                            body=body.kind, acquire_fail_at=acquire_fail_at,
                        ):
                            self.assert_rules_match_all_models(
                                frames, body, acquire_fail_at
                            )
                        cases += 1
        self.assertEqual(cases, 144)

    def test_inner_cleanup_failure_becomes_primary_for_outer_cleanup_failure(self):
        frames = (
            ResourceFrame("outer", "O", True),
            ResourceFrame("inner", "I", True),
        )
        expected = self.assert_rules_match_all_models(
            frames, BodyOutcome("result_error", {"kind": "BodyFailed"})
        )
        self.assertEqual(expected.result, {
            "error": {
                "kind": "CleanupFailed",
                "primary": {
                    "kind": "CleanupFailed",
                    "primary": {"kind": "BodyFailed"},
                    "cleanup": {"kind": "ReleaseFailed", "resource": "inner"},
                },
                "cleanup": {"kind": "ReleaseFailed", "resource": "outer"},
            }
        })

    def test_cancellation_collects_cleanup_errors_in_lifo_order(self):
        frames = (
            ResourceFrame("outer", "O", True),
            ResourceFrame("middle", "M", False),
            ResourceFrame("inner", "I", True),
        )
        expected = self.assert_rules_match_all_models(
            frames, BodyOutcome("cancelled", "stop")
        )
        self.assertEqual(expected.result, {"cancelled": {
            "reason": "stop",
            "cleanup_errors": [
                {"kind": "ReleaseFailed", "resource": "inner"},
                {"kind": "ReleaseFailed", "resource": "outer"},
            ],
        }})
        self.assertEqual(set(expected.final_resources), {"inner", "outer"})

    def test_acquisition_failure_skips_body_and_inner_acquisitions(self):
        frames = (
            ResourceFrame("outer", "O", False),
            ResourceFrame("middle", "M", False),
            ResourceFrame("inner", "I", False),
        )
        expected = self.assert_rules_match_all_models(
            frames, BodyOutcome("normal", "must-not-run"), acquire_fail_at=1
        )
        self.assertEqual(
            [event["payload"]["id"] for event in expected.events],
            ["outer", "middle", "outer"],
        )
        self.assertEqual(expected.result, {
            "error": {"kind": "AcquireFailed", "resource": "middle"}
        })

    def test_invalid_duplicate_resource_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            derive_resource_trace(
                (ResourceFrame("same", 1), ResourceFrame("same", 2)),
                BodyOutcome("normal", None),
            )


if __name__ == "__main__":
    unittest.main()
