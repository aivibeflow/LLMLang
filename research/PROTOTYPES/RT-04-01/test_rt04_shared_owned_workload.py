"""Compare two executions of a shared source-to-resource workload."""

from collections import Counter
from itertools import product
from typing import get_args
from unittest import TestCase

from rt04_backup_roles import BackupPair
from rt04_owned_call_match import MatchArm, Obligation, check_result_arms, infer_result_cases
from rt04_return_disposition import Disposition, TransferTiming
from rt04_shared_owned_transitions import execute as transition_execute
from rt04_shared_owned_workload import Inputs, SOURCE, execute, function, parse


class SharedOwnedWorkloadTests(TestCase):
    def test_all_source_workload_inputs(self):
        workload = parse(SOURCE)
        expected = {
            "before_cleanup": {"not_reached": 864, "refused": 1296, "started": 432, "erased_error": 600},
            "after_cleanup": {"not_reached": 864, "refused": 1116, "started": 612, "erased_error": 420},
        }
        for timing in get_args(TransferTiming):
            with self.subTest(timing=timing):
                counts = Counter()
                observed = set()
                for ids, wants, local, handle in product(
                    product("abc", repeat=4), (False, True), get_args(Disposition), get_args(Disposition),
                ):
                    inputs = Inputs(ids, wants, local, handle)
                    trace = execute(workload, timing, inputs)
                    self.assertEqual(trace, transition_execute(workload, timing, inputs), inputs)
                    counts[trace.second] += 1
                    if trace.result is not None:
                        observed.add(trace.result)
                        if trace.result.tag != "OkWithValue" and trace.second == "refused" and ids[2] != ids[3]:
                            counts["erased_error"] += 1
                self.assertEqual(counts, expected[timing])
                self.assertEqual(observed, infer_result_cases(function(timing)))
                self.assertEqual(len(observed), 14 if timing == "before_cleanup" else 20)

    def test_consumption_and_transfer_order_change_the_following_guard(self):
        workload = parse(SOURCE)
        inputs = Inputs(("a", "b", "c", "b"), True, "consumed_error", "consumed_error")
        early = execute(workload, "before_cleanup", inputs)
        staged = execute(workload, "after_cleanup", inputs)
        self.assertEqual(early.events[3:5], (("transfer", "handle", "ok"), ("release", "local", "consumed_error")))
        self.assertEqual(early.second, "refused")
        self.assertEqual(early.reservations, (("handle", BackupPair("a", "b")),))
        self.assertEqual(staged.cleanup_errors, (("local", "consumed_error"), ("handle", "consumed_error")))
        self.assertEqual(staged.second, "started")
        self.assertEqual(staged.reservations, (("second", BackupPair("c", "b")),))

    def test_retained_and_uncertain_dispositions_keep_the_older_roles(self):
        workload = parse(SOURCE)
        for disposition, kind in (("retained_error", "retained"), ("indeterminate", "reconcile")):
            with self.subTest(disposition=disposition):
                trace = execute(workload, "after_cleanup", Inputs(("a", "b", "c", "b"), True, "consumed_error", disposition))
                self.assertEqual(trace.result.obligations, {Obligation("handle", kind)})
                self.assertEqual(trace.second, "refused")
                self.assertEqual(trace.reservations, (("handle", BackupPair("a", "b")),))

    def test_the_proposal_uses_alias_identities_from_the_source(self):
        permitted = parse(SOURCE)
        conflicting = parse(SOURCE.replace("destination_alias = d", "destination_alias = b"))
        inputs = Inputs(("a", "b", "a", "c"), True, "ok", "ok")
        self.assertEqual(execute(permitted, "before_cleanup", inputs).second, "started")
        denied = transition_execute(conflicting, "before_cleanup", inputs)
        self.assertEqual(denied, execute(conflicting, "before_cleanup", inputs))
        self.assertEqual(denied.second, "refused")

    def test_tagged_return_can_forward_each_inferred_obligation(self):
        for timing in get_args(TransferTiming):
            with self.subTest(timing=timing):
                cases = infer_result_cases(function(timing))
                arms = tuple(MatchArm(case, tuple(sorted(item.slot for item in case.obligations))) for case in cases)
                self.assertFalse(check_result_arms(cases, arms, output="tagged_outcome"))
                issues = check_result_arms(cases, arms, output="plain_result")
                self.assertTrue(issues)
                self.assertEqual({issue.code for issue in issues}, {"ERROR_CANNOT_CARRY_OBLIGATIONS"})

    def test_parser_rejects_outside_the_shared_fragment(self):
        for source in (
            SOURCE.replace("return move(handle)", "return move(local)"),
            SOURCE.replace("destination_alias = d", "destination_alias = missing"),
            SOURCE.replace("propose(outcome,", "propose(other_result,"),
            SOURCE + "extra()\n",
        ):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    parse(source)
