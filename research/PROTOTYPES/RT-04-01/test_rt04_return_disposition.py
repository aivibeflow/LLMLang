import unittest
from itertools import product

from rt04_return_disposition import API_PROFILE_OUTCOMES, api_profile_outcome, run_return_disposition


class ReturnDispositionExperiment(unittest.TestCase):
    def test_api_profiles_preserve_documented_liveness_and_retry_rules(self):
        expected = {
            ("abstract_retained", "error"): (
                "retained_error", "live_owner", "live_resource", True,
            ),
            ("linux_close", "EIO/ENOSPC/EDQUOT/EINTR"): (
                "consumed_error", "descriptor_released", "closed", False,
            ),
            ("linux_close", "EBADF"): (
                "indeterminate", "invalid_at_entry", "not_open_at_entry", False,
            ),
            ("posix_2024_close", "EINTR"): (
                "indeterminate", "open_or_closed_or_success", "open_or_closed", False,
            ),
            ("go_os_file_close", "error"): (
                "consumed_error", "go_file_unusable", "platform-specific", False,
            ),
            ("posix_closedir", "error"): (
                "indeterminate", "dir_stream_may_be_inaccessible",
                "descriptor-closed-if-used", False,
            ),
            ("posix_fclose", "error"): (
                "consumed_error", "stdio_stream_disassociated",
                "underlying-close-error-contract", False,
            ),
        }
        self.assertEqual(len(API_PROFILE_OUTCOMES), len(expected))
        for key, (disposition, state, underlying, retry) in expected.items():
            with self.subTest(profile=key):
                item = api_profile_outcome(*key)
                self.assertEqual(
                    (item.disposition, item.capability_state, item.underlying_state,
                     item.retry_allowed),
                    (disposition, state, underlying, retry),
                )
                self.assertTrue(item.error_obligation)
        with self.assertRaisesRegex(ValueError, "unsupported API profile"):
            api_profile_outcome("unknown", "error")

    def test_transfer_before_cleanup_preserves_disposition_of_local(self):
        trace = run_return_disposition(
            body="success", transfer_timing="before_cleanup",
            local_disposition="consumed_error", caller_action="propagate",
            output_carries_owned=True,
        )
        self.assertEqual(trace.tag, "CleanupFailedWithValue")
        self.assertEqual(trace.caller_owner, "upstream")
        self.assertEqual(dict(trace.resource_states), {
            "handle": "upstream_owned", "local": "consumed_with_error",
        })
        self.assertEqual(trace.errors, ("local:consumed_error",))

    def test_staged_cleanup_failure_keeps_pending_handle_disposition_separate(self):
        trace = run_return_disposition(
            body="success", transfer_timing="after_cleanup",
            local_disposition="retained_error",
            pending_handle_disposition="consumed_error",
        )
        self.assertEqual(trace.tag, "StagedCleanupFailedWithoutValue")
        self.assertEqual(trace.caller_owner, "none")
        self.assertEqual(dict(trace.resource_states), {
            "handle": "consumed_with_error", "local": "live_cleanup_debt",
        })
        self.assertEqual(trace.errors, ("local:retained_error", "handle:consumed_error"))

    def test_domain_error_before_transfer_can_leave_multiple_distinct_debts(self):
        trace = run_return_disposition(
            body="domain_error_before_transfer", transfer_timing="after_cleanup",
            local_disposition="retained_error", pending_handle_disposition="indeterminate",
        )
        self.assertEqual(trace.tag, "ErrWithCleanupErrors")
        self.assertEqual(trace.caller_owner, "none")
        self.assertEqual(trace.errors, (
            "domain_error", "local:retained_error", "handle:indeterminate",
        ))
        self.assertEqual(dict(trace.resource_states)["local"], "live_cleanup_debt")
        self.assertEqual(dict(trace.resource_states)["handle"], "ownership_unknown")

    def test_domain_error_after_transfer_keeps_returned_handle_and_primary_error(self):
        trace = run_return_disposition(
            body="domain_error_after_transfer", transfer_timing="before_cleanup",
            local_disposition="consumed_error",
        )
        self.assertEqual(trace.tag, "DomainAndCleanupFailedWithValue")
        self.assertEqual(trace.caller_owner, "caller")
        self.assertEqual(trace.errors, ("domain_error", "local:consumed_error"))

    def test_caller_release_disposition_does_not_conflate_error_and_liveness(self):
        expected_owner = {
            "ok": "none", "retained_error": "caller_cleanup_debt",
            "consumed_error": "none", "indeterminate": "unknown",
        }
        for disposition, owner in expected_owner.items():
            with self.subTest(disposition=disposition):
                trace = run_return_disposition(
                    body="success", transfer_timing="before_cleanup",
                    local_disposition="ok", caller_action="release",
                    caller_disposition=disposition,
                )
                self.assertEqual(trace.caller_owner, owner)
                self.assertEqual(dict(trace.resource_states)["handle"], {
                    "ok": "released", "retained_error": "live_cleanup_debt",
                    "consumed_error": "consumed_with_error", "indeterminate": "ownership_unknown",
                }[disposition])

    def test_bounded_cross_product_has_consistent_call_boundary_states(self):
        bodies = (
            ("success", "before_cleanup"),
            ("success", "after_cleanup"),
            ("domain_error_before_transfer", "after_cleanup"),
            ("domain_error_after_transfer", "before_cleanup"),
        )
        dispositions = ("ok", "retained_error", "consumed_error", "indeterminate")
        actions = ("none", "release", "propagate", "ignore")
        comparisons = 0
        for (body, timing), local, pending, action, caller, carries in product(
            bodies, dispositions, dispositions, actions, dispositions, (False, True)
        ):
            trace = run_return_disposition(
                body=body, transfer_timing=timing, local_disposition=local,
                pending_handle_disposition=pending, caller_action=action,
                caller_disposition=caller, output_carries_owned=carries,
            )
            states = dict(trace.resource_states)
            if trace.caller_owner == "upstream":
                self.assertEqual(states["handle"], "upstream_owned")
            if "PROPAGATION_DROPS_OWNERSHIP" in trace.findings:
                self.assertEqual(action, "propagate")
                self.assertFalse(carries)
            if "LEAKED_OWNERSHIP" in trace.findings:
                self.assertEqual(action, "ignore")
            comparisons += 1
        self.assertEqual(comparisons, 4 * 4 * 4 * 4 * 4 * 2)

    def test_rejects_incompatible_error_timing(self):
        with self.assertRaisesRegex(ValueError, "requires before-cleanup"):
            run_return_disposition(
                body="domain_error_after_transfer", transfer_timing="after_cleanup",
                local_disposition="ok",
            )


if __name__ == "__main__":
    unittest.main()
