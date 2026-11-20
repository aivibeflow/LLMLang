import unittest
from dataclasses import replace
from itertools import combinations, product
from typing import get_args

from rt04_owned_call_match import (
    Function, IfFlag, MatchArm, MatchCall, MatchIssue, Obligation, ResultCase,
    ReturnError, ReturnOwned, WithOwned, check_match, execute_match,
    infer_result_cases, observe_call,
)
from rt04_return_disposition import Disposition, TransferTiming


def resource_function(transfer, local_close, handle_close, *, handle="fd", local="scratch"):
    return Function(
        "open_handle",
        WithOwned(handle, handle_close, WithOwned(
            local, local_close, IfFlag(ReturnError(), ReturnOwned(handle)),
        )),
        transfer,
    )


def forward_every_case(function, output="tagged_outcome"):
    return MatchCall(function.name, tuple(
        MatchArm(case, tuple(sorted(obligation.slot for obligation in case.obligations)))
        for case in infer_result_cases(function)
    ), output)


def issue_codes(issues):
    return {issue.code for issue in issues}


class OwnedCallMatchExperiment(unittest.TestCase):
    def test_inference_matches_runtime_and_compares_both_output_types(self):
        dispositions = get_args(Disposition)
        contracts = tuple(
            frozenset(outcomes)
            for size in range(1, len(dispositions) + 1)
            for outcomes in combinations(dispositions, size)
        )
        executions = 0
        plain_accepted = {timing: 0 for timing in get_args(TransferTiming)}
        for local, handle, timing in product(contracts, contracts, get_args(TransferTiming)):
            function = resource_function(timing, local, handle)
            observed = set()
            for flag, local_result, handle_result in product((False, True), local, handle):
                trace = observe_call(function, flag=flag, local_close=local_result, handle_close=handle_result)
                observed.add(trace.case)
                executions += 1
            with self.subTest(local=local, handle=handle, timing=timing):
                self.assertEqual(infer_result_cases(function), observed)
                tagged = forward_every_case(function)
                self.assertFalse(check_match(function, tagged))
                plain = replace(tagged, output="plain_result")
                issues = check_match(function, plain)
                if issues:
                    self.assertEqual(issue_codes(issues), {"ERROR_CANNOT_CARRY_OBLIGATIONS"})
                else:
                    plain_accepted[timing] += 1
        self.assertEqual(executions, 4096)
        self.assertEqual(plain_accepted, {"before_cleanup": 3, "after_cleanup": 9})

    def test_transfer_first_can_forward_a_value_and_a_separate_live_debt(self):
        function = resource_function("before_cleanup", frozenset({"retained_error"}), frozenset({"ok"}))
        call = forward_every_case(function)
        result = execute_match(function, call, flag=False, local_close="retained_error", handle_close="ok")
        self.assertEqual(result.case, ResultCase("CleanupFailedWithValue", frozenset({
            Obligation("handle", "owned"), Obligation("local", "retained"),
        })))
        self.assertFalse(result.domain_error)
        self.assertEqual(result.cleanup_errors, (("scratch", "retained_error"),))
        self.assertEqual(result.events, (
            ("acquire", "fd", "ok"), ("acquire", "scratch", "ok"), ("transfer", "fd", "ok"),
            ("release", "scratch", "retained_error"), ("forward", "handle", "owned"),
            ("forward", "local", "retained"),
        ))

    def test_staged_failure_keeps_pending_handle_debt_and_uncertainty_distinct(self):
        function = resource_function(
            "after_cleanup", frozenset({"indeterminate"}), frozenset({"retained_error", "indeterminate"}),
        )
        call = forward_every_case(function)
        for disposition, kind in (("retained_error", "retained"), ("indeterminate", "reconcile")):
            result = execute_match(function, call, flag=False, local_close="indeterminate", handle_close=disposition)
            with self.subTest(disposition=disposition):
                self.assertEqual(result.case, ResultCase("StagedCleanupFailedWithoutValue", frozenset({
                    Obligation("handle", kind), Obligation("local", "reconcile"),
                })))
                self.assertEqual(result.cleanup_errors, (("scratch", "indeterminate"), ("fd", disposition)))
                self.assertNotIn("transfer", {action for action, _, _ in result.events})

    def test_consumed_failures_keep_both_diagnostics_without_ownership(self):
        function = resource_function("after_cleanup", frozenset({"consumed_error"}), frozenset({"consumed_error"}))
        call = forward_every_case(function, "plain_result")
        result = execute_match(function, call, flag=True, local_close="consumed_error", handle_close="consumed_error")
        self.assertEqual(result.case, ResultCase("Err"))
        self.assertTrue(result.domain_error)
        self.assertEqual(result.cleanup_errors, (("scratch", "consumed_error"), ("fd", "consumed_error")))
        self.assertFalse(any(action == "forward" for action, _, _ in result.events))

    def test_widest_contract_requires_different_numbers_of_exact_arms(self):
        outcomes = frozenset(get_args(Disposition))
        for timing, count in (("before_cleanup", 14), ("after_cleanup", 20)):
            with self.subTest(timing=timing):
                function = resource_function(timing, outcomes, outcomes)
                call = forward_every_case(function)
                self.assertEqual(len(call.arms), count)
                self.assertFalse(check_match(function, call))

    def test_timing_changes_plain_result_feasibility_for_the_same_close_contract(self):
        local, handle = frozenset({"ok", "consumed_error"}), frozenset({"ok"})
        staged = resource_function("after_cleanup", local, handle)
        early = replace(staged, transfer="before_cleanup")
        self.assertFalse(check_match(staged, forward_every_case(staged, "plain_result")))
        case = ResultCase(
            "CleanupFailedWithValue", frozenset({Obligation("handle", "owned")}),
        )
        self.assertEqual(check_match(early, forward_every_case(early, "plain_result")), {
            MatchIssue("ERROR_CANNOT_CARRY_OBLIGATIONS", case),
        })

    def test_match_rejects_lost_duplicate_and_nonexistent_obligations(self):
        function = resource_function("before_cleanup", frozenset({"indeterminate"}), frozenset({"ok"}))
        call = forward_every_case(function)
        row = next(arm for arm in call.arms if arm.pattern.tag == "CleanupFailedWithValue")
        rest = tuple(arm for arm in call.arms if arm is not row)
        for arms, code in (
            (rest, "MISSING_ARM"), (call.arms + (row,), "DUPLICATE_ARM"),
            (rest + (replace(row, moves=("handle",)),), "MISSING_MOVE"),
            (rest + (replace(row, moves=("handle", "local", "local")),), "DUPLICATE_MOVE"),
            (rest + (replace(row, moves=("handle", "local", "other")),), "MOVE_WITHOUT_OBLIGATION"),
        ):
            with self.subTest(code=code):
                self.assertEqual(issue_codes(check_match(function, replace(call, arms=arms))), {code})

        claimed_live = ResultCase(row.pattern.tag, frozenset({Obligation("handle", "owned"), Obligation("local", "owned")}))
        forged = replace(call, arms=rest + (replace(row, pattern=claimed_live),))
        self.assertEqual(issue_codes(check_match(function, forged)), {"MISSING_ARM", "UNEXPECTED_ARM"})

    def test_private_binding_names_do_not_change_the_result_type(self):
        local, handle = frozenset({"ok", "indeterminate"}), frozenset({"ok", "retained_error"})
        before = resource_function("after_cleanup", local, handle)
        after = resource_function("after_cleanup", local, handle, handle="resource", local="temp")
        self.assertEqual(infer_result_cases(before), infer_result_cases(after))
        self.assertFalse(check_match(after, forward_every_case(before)))

    def test_contract_expansion_requires_an_arm_even_when_tags_stay_the_same(self):
        before = resource_function("after_cleanup", frozenset({"consumed_error"}), frozenset({"ok"}))
        after = resource_function("after_cleanup", frozenset({"consumed_error", "retained_error"}), frozenset({"ok"}))
        old_cases, new_cases = infer_result_cases(before), infer_result_cases(after)
        self.assertLess(old_cases, new_cases)
        self.assertEqual({case.tag for case in old_cases}, {case.tag for case in new_cases})
        self.assertEqual(check_match(after, forward_every_case(before)), {
            MatchIssue("MISSING_ARM", case) for case in new_cases - old_cases
        })

    def test_rejects_wrong_move_target_contract_and_call_name(self):
        function = resource_function("after_cleanup", frozenset({"ok"}), frozenset({"ok"}))
        inner = replace(function.body.body, body=ReturnOwned("scratch"))
        wrong_move = replace(function, body=replace(function.body, body=inner))
        with self.assertRaisesRegex(ValueError, "only the outer binding"):
            infer_result_cases(wrong_move)
        with self.assertRaisesRegex(ValueError, "outside the declared contract"):
            observe_call(function, flag=False, local_close="retained_error", handle_close="ok")
        with self.assertRaisesRegex(ValueError, "unresolved call"):
            check_match(function, replace(forward_every_case(function), callee="missing"))


if __name__ == "__main__":
    unittest.main()
