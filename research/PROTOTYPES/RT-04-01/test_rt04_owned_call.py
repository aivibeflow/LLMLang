import unittest

from rt04_owned_call import (
    check_owned_call,
    check_owned_call_cfg,
    check_owned_call_tree,
    execute_owned_call_tree,
)
from rt03_return_cleanup import run_return_cleanup


HANDLE_RESULT = {"Result": [{"Owned": "Handle"}, "String"]}
HANDLE_WITH_CLEANUP_ERROR = {
    "ErrorWithValue": [{"Owned": "Handle"}, "String", "CleanupError"]
}


class OwnedCallBoundary(unittest.TestCase):
    def test_result_success_requires_consuming_owned_value(self):
        result = check_owned_call(HANDLE_RESULT, {
            "ok": {"actions": ["release"]},
            "error": {"actions": []},
        })
        self.assertEqual(result.status, "ACCEPTED")
        self.assertEqual(dict(result.terminal_owners), {"error": "none", "ok": "released"})

    def test_error_with_value_requires_cleanup_on_both_owned_paths(self):
        result = check_owned_call(HANDLE_WITH_CLEANUP_ERROR, {
            "ok": {"actions": ["transfer"]},
            "error_with_value": {"actions": ["release"]},
        })
        self.assertEqual(result.status, "ACCEPTED")

    def test_propagation_must_preserve_owned_value_in_output_type(self):
        safe = check_owned_call(HANDLE_WITH_CLEANUP_ERROR, {
            "ok": {"actions": ["release"]},
            "error_with_value": {
                "actions": ["propagate_owned"], "output_carries_owned": True,
            },
        })
        unsafe = check_owned_call(HANDLE_WITH_CLEANUP_ERROR, {
            "ok": {"actions": ["release"]},
            "error_with_value": {"actions": ["propagate_owned"]},
        })
        self.assertEqual(safe.status, "ACCEPTED")
        self.assertIn("error_with_value:PROPAGATION_DROPS_OWNERSHIP", unsafe.findings)

    def test_rejects_drop_duplicate_and_use_after_move(self):
        cases = [
            (["ignore"], "ok:LEAKED_OWNERSHIP"),
            (["duplicate", "release"], "ok:DUPLICATE_OWNER"),
            (["transfer", "use"], "ok:USE_AFTER_MOVE"),
            (["release", "transfer"], "ok:MULTIPLE_CONSUMPTIONS"),
        ]
        for actions, finding in cases:
            with self.subTest(actions=actions):
                result = check_owned_call(HANDLE_RESULT, {
                    "ok": {"actions": actions}, "error": {"actions": []},
                })
                self.assertEqual(result.status, "REJECTED")
                self.assertIn(finding, result.findings)

    def test_unknown_type_and_missing_outcome_fail_closed(self):
        unknown = check_owned_call({"Result": ["Int", "String"]}, {
            "ok": {"actions": []}, "error": {"actions": []},
        })
        incomplete = check_owned_call(HANDLE_RESULT, {
            "ok": {"actions": ["release"]},
        })
        self.assertEqual(unknown.status, "UNKNOWN")
        self.assertEqual(incomplete.status, "UNKNOWN")

    def test_invalid_envelope_is_not_silently_accepted(self):
        with self.assertRaisesRegex(ValueError, "boolean"):
            check_owned_call(HANDLE_WITH_CLEANUP_ERROR, {
                "ok": {"actions": ["release"]},
                "error_with_value": {
                    "actions": ["propagate_owned"], "output_carries_owned": 1,
                },
            })

    def test_cfg_checks_both_result_outcomes_and_all_terminal_paths(self):
        result = check_owned_call_cfg(HANDLE_RESULT, {
            "ok": {"entry": "start", "output_carries_owned": False, "blocks": {
                "start": {"actions": ["use"], "successors": ["release"]},
                "release": {"actions": ["release"]},
            }},
            "error": {"entry": "start", "output_carries_owned": False, "blocks": {
                "start": {},
            }},
        })
        self.assertEqual(result.status, "ACCEPTED")

    def test_cfg_rejects_inconsistent_join_ownership(self):
        cfg = {"entry": "branch", "output_carries_owned": False, "blocks": {
            "branch": {"successors": ["release_path", "transfer_path"]},
            "release_path": {"actions": ["release"], "successors": ["join"]},
            "transfer_path": {"actions": ["transfer"], "successors": ["join"]},
            "join": {"actions": ["release"]},
        }}
        result = check_owned_call_cfg(HANDLE_WITH_CLEANUP_ERROR, {
            "ok": {**cfg, "blocks": {"exit": {"actions": ["release"]}}, "entry": "exit"},
            "error_with_value": cfg,
        })
        self.assertEqual(result.status, "REJECTED")
        self.assertTrue(any("OWNERSHIP_JOIN_MISMATCH" in f for f in result.findings))

    def test_cfg_rejects_leak_and_use_after_move_and_marks_cycles_unknown(self):
        def one(actions, successors=None):
            return {"entry": "entry", "output_carries_owned": False, "blocks": {
                "entry": {"actions": actions, "successors": successors or []},
            }}
        leak = check_owned_call_cfg(HANDLE_RESULT, {
            "ok": one([]), "error": one([]),
        })
        moved = check_owned_call_cfg(HANDLE_RESULT, {
            "ok": one(["transfer", "use"]), "error": one([]),
        })
        cycle_cfg = {"entry": "loop", "output_carries_owned": False, "blocks": {
            "loop": {"actions": ["release"], "successors": ["loop"]},
        }}
        cycle = check_owned_call_cfg(HANDLE_RESULT, {
            "ok": cycle_cfg, "error": one([]),
        })
        self.assertIn("ok:entry:LEAKED_OWNERSHIP", leak.findings)
        self.assertIn("ok:entry:USE_AFTER_MOVE", moved.findings)
        self.assertEqual(cycle.status, "UNKNOWN")

    def test_successful_caller_cleanup_agrees_with_transfer_first_trace(self):
        trace = run_return_cleanup(
            "transfer_then_cleanup", temporary_release_fails=True,
            caller_exits_after_return=True,
        )
        self.assertEqual(trace.outcome, "error_with_value")
        self.assertEqual(trace.returned, "handle")
        self.assertEqual(dict(trace.owners), {"temporary": "callee_cleanup_debt"})
        self.assertIn(("release", "handle", "ok"), tuple(
            (event.operation, event.resource, event.outcome) for event in trace.events
        ))
        caller = check_owned_call_cfg(HANDLE_WITH_CLEANUP_ERROR, {
            "ok": {"entry": "exit", "output_carries_owned": False,
                   "blocks": {"exit": {"actions": ["release"]}}},
            "error_with_value": {"entry": "exit", "output_carries_owned": False,
                                 "blocks": {"exit": {"actions": ["release"]}}},
        })
        self.assertEqual(caller.status, "ACCEPTED")

    def test_release_failure_is_not_represented_by_current_cfg_action(self):
        trace = run_return_cleanup(
            "transfer_then_cleanup", temporary_release_fails=True,
            handle_release_fails=True, caller_exits_after_return=True,
        )
        self.assertEqual(dict(trace.owners), {
            "handle": "caller_cleanup_debt", "temporary": "callee_cleanup_debt",
        })
        static = check_owned_call_cfg(HANDLE_WITH_CLEANUP_ERROR, {
            "ok": {"entry": "exit", "output_carries_owned": False,
                   "blocks": {"exit": {"actions": ["release"]}}},
            "error_with_value": {"entry": "exit", "output_carries_owned": False,
                                 "blocks": {"exit": {"actions": ["release"]}}},
        })
        # The current CFG model treats release as infallible, so it accepts
        # despite the operational trace retaining caller cleanup debt.
        self.assertEqual(static.status, "ACCEPTED")

    def test_cfg_release_attempt_branches_and_preserves_debt(self):
        cfg = {"entry": "attempt", "output_carries_owned": True, "blocks": {
            "attempt": {"release_attempt": True,
                        "successors": {"ok": "released", "error": "cleanup_error"}},
            "released": {},
            "cleanup_error": {"actions": ["propagate_owned"]},
        }}
        result = check_owned_call_cfg(HANDLE_WITH_CLEANUP_ERROR, {
            "ok": cfg, "error_with_value": cfg,
        })
        self.assertEqual(result.status, "ACCEPTED")
        self.assertIn(("error_with_value", "caller_output_cleanup_debt"), result.terminal_owners)

    def test_cfg_release_attempt_rejects_dropped_failure_debt(self):
        cfg = {"entry": "attempt", "output_carries_owned": False, "blocks": {
            "attempt": {"release_attempt": True,
                        "successors": {"ok": "released", "error": "failed"}},
            "released": {},
            "failed": {},
        }}
        result = check_owned_call_cfg(HANDLE_WITH_CLEANUP_ERROR, {
            "ok": cfg, "error_with_value": cfg,
        })
        self.assertEqual(result.status, "REJECTED")
        self.assertTrue(any("LEAKED_CLEANUP_DEBT" in finding for finding in result.findings))

    def test_structured_call_tree_lowers_fallible_cleanup_to_checked_cfg(self):
        tree = {"release_attempt": {
            "ok": {"sequence": []},
            "error": "propagate_owned",
        }}
        result = check_owned_call_tree(HANDLE_WITH_CLEANUP_ERROR, {
            "ok": {"body": tree, "output_carries_owned": True},
            "error_with_value": {"body": tree, "output_carries_owned": True},
        })
        self.assertEqual(result.status, "ACCEPTED")
        self.assertIn(("error_with_value", "caller_output_cleanup_debt"), result.terminal_owners)

    def test_structured_conditional_with_incompatible_join_is_rejected(self):
        tree = {"sequence": [
            {"if": ["release", "transfer"]},
            "release",
        ]}
        result = check_owned_call_tree(HANDLE_WITH_CLEANUP_ERROR, {
            "ok": {"body": tree, "output_carries_owned": False},
            "error_with_value": {"body": "release", "output_carries_owned": False},
        })
        self.assertEqual(result.status, "REJECTED")
        self.assertTrue(any("OWNERSHIP_JOIN_MISMATCH" in finding for finding in result.findings))

    def test_unsupported_structured_tree_fails_closed(self):
        result = check_owned_call_tree(HANDLE_RESULT, {
            "ok": {"body": {"loop": "unknown"}, "output_carries_owned": False},
            "error": {"body": {"sequence": []}, "output_carries_owned": False},
        })
        self.assertEqual(result.status, "UNKNOWN")

    def test_same_structured_tree_drives_static_and_dynamic_ownership_results(self):
        tree = {"release_attempt": {
            "ok": {"sequence": []},
            "error": "propagate_owned",
        }}
        static = check_owned_call_tree(HANDLE_WITH_CLEANUP_ERROR, {
            "ok": {"body": tree, "output_carries_owned": True},
            "error_with_value": {"body": tree, "output_carries_owned": True},
        })
        succeeded = execute_owned_call_tree(
            tree, release_results=[True], output_carries_owned=True,
        )
        failed = execute_owned_call_tree(
            tree, release_results=[False], output_carries_owned=True,
        )
        self.assertEqual(static.status, "ACCEPTED")
        self.assertEqual(succeeded.terminal_owner, "released")
        self.assertEqual(succeeded.events, ("release:ok",))
        self.assertEqual(failed.terminal_owner, "caller_output_cleanup_debt")
        self.assertEqual(failed.events, ("release:error", "propagate_owned"))
        self.assertEqual(failed.status, "ACCEPTED")

    def test_result_error_has_no_owned_value_but_error_with_value_does(self):
        no_value = {"sequence": []}
        result_tree = check_owned_call_tree(HANDLE_RESULT, {
            "ok": {"body": "release", "output_carries_owned": False},
            "error": {"body": no_value, "output_carries_owned": False},
        })
        bad_result_tree = check_owned_call_tree(HANDLE_RESULT, {
            "ok": {"body": "release", "output_carries_owned": False},
            "error": {"body": "release", "output_carries_owned": False},
        })
        bad_error_with_value = check_owned_call_tree(HANDLE_WITH_CLEANUP_ERROR, {
            "ok": {"body": "release", "output_carries_owned": False},
            "error_with_value": {"body": no_value, "output_carries_owned": False},
        })
        runtime_error = execute_owned_call_tree(
            no_value, release_results=[], owned_on_entry=False,
        )
        self.assertEqual(result_tree.status, "ACCEPTED")
        self.assertTrue(any("error:" in finding and "ACTION_WITHOUT_OWNED_VALUE" in finding
                            for finding in bad_result_tree.findings))
        self.assertIn("error_with_value", " ".join(bad_error_with_value.findings))
        self.assertEqual(runtime_error.status, "ACCEPTED")
        self.assertEqual(runtime_error.terminal_owner, "none")

    def test_malformed_and_unrecognized_outcome_tags_are_unknown(self):
        missing_cleanup_error = check_owned_call_tree(HANDLE_WITH_CLEANUP_ERROR, {
            "ok": {"body": "release", "output_carries_owned": False},
            "error": {"body": "release", "output_carries_owned": False},
        })
        unknown_tag = check_owned_call_tree(HANDLE_RESULT, {
            "ok": {"body": "release", "output_carries_owned": False},
            "cancelled": {"body": {"sequence": []}, "output_carries_owned": False},
        })
        self.assertEqual(missing_cleanup_error.status, "UNKNOWN")
        self.assertEqual(unknown_tag.status, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
