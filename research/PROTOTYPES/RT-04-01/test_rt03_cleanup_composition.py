import unittest
from itertools import product

from rt03_cleanup_composition import CleanupAction, compose_cleanup_outcome
from rt03_cleanup_composition_audit import audit_obligations


POLICIES = ("P", "A", "N", "R", "D", "X")


def actions(results, dispositions):
    return tuple(
        CleanupAction(name, result, disposition)
        for name, result, disposition in zip(("inner", "outer"), results, dispositions)
    )


DISCRIMINATORS = (
    ("CLEANUP-OUT-001", "return", "v", ("error", "ok"), ("retained", "released"), 2, False, "transfer_first", ()),
    ("CLEANUP-OUT-002", "return", "v", ("error", "error"), ("retained", "consumed"), 2, False, "transfer_first", ()),
    ("CLEANUP-OUT-003", "domain_error", "E0", ("error", "error"), ("retained", "indeterminate"), 2, False, "transfer_first", ()),
    ("CLEANUP-OUT-004", "return", "v", ("error", "ok"), ("retained", "released"), 2, True, "transfer_first", ()),
    ("CLEANUP-OUT-005", "domain_error", "E0", ("error", "ok"), ("retained", "released"), 2, True, "transfer_first", ()),
    ("CLEANUP-OUT-006", "return", "v", ("error", "ok"), ("retained", "released"), 2, True, "stage_until_cleanup", ()),
    ("CLEANUP-OUT-007", "cancellation", "cancel-1", ("error", "error"), ("retained", "consumed"), 2, False, "transfer_first", ()),
    ("CLEANUP-OUT-008", "fuel", "budget-0", ("error", "ok"), ("retained", "released"), 2, False, "transfer_first", ("write:before-cleanup",)),
    ("CLEANUP-OUT-009", "fuel", "budget-0", ("error", "ok"), ("retained", "released"), 0, True, "transfer_first", ("write:before-cleanup",)),
    ("CLEANUP-OUT-010", "panic", "P0", ("panic", "error"), ("indeterminate", "retained"), 2, False, "transfer_first", ()),
    ("CLEANUP-OUT-011", "domain_error", "E0", ("error", "ok"), ("retained", "released"), 2, False, "transfer_first", ()),
    ("CLEANUP-OUT-012", "return", "v", ("error", "ok"), ("consumed", "released"), 2, False, "transfer_first", ()),
)


class CleanupCompositionExperiment(unittest.TestCase):
    def test_twelve_discriminators_cross_all_six_candidate_policies(self):
        count = 0
        for case_id, primary, payload, results, disposition, budget, owned, timing, effects in DISCRIMINATORS:
            for policy in POLICIES:
                observation = compose_cleanup_outcome(
                    primary, payload, actions(results, disposition), policy=policy,
                    cleanup_budget=budget, owned_value=owned,
                    transfer_timing=timing, effects=effects,
                )
                issues = audit_obligations(observation, ("inner", "outer"), budget)
                self.assertEqual(issues, (), f"{case_id}/{policy}: {issues}")
                self.assertEqual(observation.primary_kind, primary, case_id)
                self.assertEqual(observation.effects, effects, case_id)
                count += 1
        self.assertEqual(count, 72)

    def test_composition_vectors_have_distinguishable_cause_carriers(self):
        shared = actions(("error", "error"), ("retained", "consumed"))
        observed = {
            policy: compose_cleanup_outcome(
                "domain_error", "E0", shared, policy=policy, cleanup_budget=2,
            )
            for policy in POLICIES
        }
        self.assertEqual(observed["P"].suppressed_causes, (
            "cleanup:inner:error", "cleanup:outer:error",
        ))
        self.assertEqual(observed["A"].aggregate_causes, (
            "domain_error:E0", "cleanup:inner:error", "cleanup:outer:error",
        ))
        self.assertEqual(observed["N"].nested_cleanup_causes, (
            "cleanup:inner:error", "cleanup:outer:error",
        ))
        self.assertEqual(observed["R"].terminal_kind, "cleanup_error")
        self.assertEqual(observed["R"].terminal_payload, "cleanup:outer:error")
        self.assertEqual(observed["R"].replaced_primary, "domain_error:E0")
        self.assertEqual(observed["D"].suppressed_causes, ())
        self.assertEqual(observed["D"].aggregate_causes, ())
        self.assertEqual(observed["D"].nested_cleanup_causes, ())
        self.assertTrue(all(o.cleanup_trace == observed["P"].cleanup_trace for o in observed.values()))
        self.assertTrue(all(o.owners == observed["P"].owners for o in observed.values()))

    def test_cleanup_panic_aborts_only_when_unwind_is_already_active_under_x(self):
        fatal = actions(("panic", "ok"), ("indeterminate", "released"))
        for policy in POLICIES:
            result = compose_cleanup_outcome(
                "panic", "P0", fatal, policy=policy, cleanup_budget=2,
            )
            if policy == "X":
                self.assertEqual(result.terminal_kind, "abort")
            elif policy == "R":
                self.assertEqual(result.terminal_kind, "cleanup_error")
            else:
                self.assertEqual(result.terminal_kind, "panic")
        ordinary = actions(("error", "ok"), ("retained", "released"))
        x_result = compose_cleanup_outcome(
            "panic", "P0", ordinary, policy="X", cleanup_budget=2,
        )
        self.assertEqual(x_result.terminal_kind, "panic")
        normal_exit = compose_cleanup_outcome(
            "return", "v", fatal, policy="X", cleanup_budget=2,
        )
        self.assertEqual(normal_exit.terminal_kind, "panic")
        self.assertNotEqual(normal_exit.terminal_kind, "abort")

    def test_exhaustive_small_product_keeps_obligation_projection_consistent(self):
        # Valid action shapes: successful release, or a failed action with
        # retained/consumed/indeterminate disposition. Transfer timing is
        # varied only when there is an owned value.
        action_options = (
            ("ok", "released"),
            *((kind, disposition)
              for kind in ("error", "panic")
              for disposition in ("retained", "consumed", "indeterminate")),
        )
        primary_kinds = ("return", "domain_error", "cancellation", "fuel", "panic")
        checked = 0
        ownership_modes = (
            (False, "transfer_first"),
            (True, "transfer_first"),
            (True, "stage_until_cleanup"),
        )
        for primary, policy, action_vector, budget, (owned, timing) in product(
            primary_kinds,
            POLICIES,
            product(action_options, repeat=2),
            range(3),
            ownership_modes,
        ):
            cleanup_actions = tuple(
                CleanupAction(name, result, disposition)
                for name, (result, disposition) in zip(("inner", "outer"), action_vector)
            )
            observation = compose_cleanup_outcome(
                primary, "fixture", cleanup_actions,
                policy=policy, cleanup_budget=budget, owned_value=owned,
                transfer_timing=timing,
            )
            issues = audit_obligations(observation, ("inner", "outer"), budget)
            self.assertEqual(issues, (), f"{primary}/{policy}/{action_vector}/{budget}/{owned}/{timing}: {issues}")
            checked += 1
        self.assertEqual(checked, 13230)


if __name__ == "__main__":
    unittest.main()
