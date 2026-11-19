import unittest
from itertools import product

from rt04_cleanup_disposition import run_cleanup_stack


class CleanupDispositionExperiment(unittest.TestCase):
    def test_lifo_trace_separates_resource_state_from_cleanup_error(self):
        trace = run_cleanup_stack(
            ("outer", "handle", "inner"),
            {"outer": "ok", "handle": "consumed_error", "inner": "retained_error"},
        )
        self.assertEqual(trace.events, (
            ("inner", "retained_error"),
            ("handle", "consumed_error"),
            ("outer", "ok"),
        ))
        self.assertEqual(trace.retained, ("inner",))
        self.assertEqual(trace.consumed_with_error, ("handle",))
        self.assertEqual(trace.released, ("outer",))
        self.assertEqual(trace.error_order, ("inner", "handle"))

    def test_indeterminate_disposition_never_claims_live_or_consumed(self):
        trace = run_cleanup_stack(("resource",), {"resource": "indeterminate"})
        self.assertEqual(trace.indeterminate, ("resource",))
        self.assertEqual(trace.retained, ())
        self.assertEqual(trace.consumed_with_error, ())

    def test_unwind_policy_controls_outer_cleanup_after_failure(self):
        inputs = {"outer": "ok", "middle": "consumed_error", "inner": "ok"}
        continued = run_cleanup_stack(("outer", "middle", "inner"), inputs)
        stopped = run_cleanup_stack(("outer", "middle", "inner"), inputs,
                                    unwind_policy="stop")
        self.assertEqual(continued.released, ("inner", "outer"))
        self.assertEqual(stopped.released, ("inner",))
        self.assertEqual(stopped.not_attempted, ("outer",))
        self.assertEqual(stopped.error_order, ("middle",))

    def test_bounded_disposition_space_preserves_each_resource_class(self):
        values = ("ok", "retained_error", "consumed_error", "indeterminate")
        for depth in range(1, 4):
            resources = tuple(f"r{i}" for i in range(depth))
            cases = 0
            for vector in product(values, repeat=depth):
                for policy in ("continue", "stop"):
                    trace = run_cleanup_stack(resources, dict(zip(resources, vector)),
                                              unwind_policy=policy)
                    reverse_vector = tuple(reversed(vector))
                    attempted = depth
                    if policy == "stop":
                        attempted = next((i + 1 for i, outcome in enumerate(reverse_vector)
                                          if outcome != "ok"), depth)
                    attempted_results = reverse_vector[:attempted]
                    self.assertEqual(trace.events, tuple(zip(reversed(resources), attempted_results)))
                    self.assertEqual(len(trace.not_attempted), depth - attempted)
                    self.assertEqual(len(trace.released), attempted_results.count("ok"))
                    self.assertEqual(len(trace.retained), attempted_results.count("retained_error"))
                    self.assertEqual(len(trace.consumed_with_error), attempted_results.count("consumed_error"))
                    self.assertEqual(len(trace.indeterminate), attempted_results.count("indeterminate"))
                    self.assertEqual(len(trace.error_order), attempted - attempted_results.count("ok"))
                    cases += 1
            self.assertEqual(cases, 2 * 4 ** depth)

    def test_rejects_missing_extra_or_ambiguous_dispositions(self):
        with self.assertRaisesRegex(ValueError, "one supported result"):
            run_cleanup_stack(("r",), {})
        with self.assertRaisesRegex(ValueError, "unique non-empty"):
            run_cleanup_stack(("r", "r"), {"r": "ok"})
        with self.assertRaisesRegex(ValueError, "one supported result"):
            run_cleanup_stack(("r",), {"r": "error"})


if __name__ == "__main__":
    unittest.main()
