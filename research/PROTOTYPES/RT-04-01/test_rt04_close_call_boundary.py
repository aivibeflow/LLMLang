"""Check the resource outcomes and forwarding arms of one shared workload."""

from collections import Counter
from typing import get_args
from unittest import TestCase

from rt04_close_call_boundary import ClosePolicy, compare, fixtures
from rt04_owned_call_match import MatchArm, MatchIssue, Obligation, ResultCase, check_result_arms
from rt04_sqlite_recovery import BUSY, ERROR, OK, CleanupCall


class CloseBoundaryTests(TestCase):
    def test_same_corpus_distinguishes_admission_and_completion(self):
        corpus = tuple(fixtures())
        self.assertEqual(len({case.proof.inputs for case in corpus}), 16)
        self.assertEqual(len(corpus), 36)
        expected = {
            "source_proof": {"source_rejected": 30, "closed_destroyed": 6},
            "checked_snapshot": {"stale_snapshot": 17, "nonempty_snapshot": 12, "closed_destroyed": 7},
            "recover_busy": {"busy": 24, "closed_destroyed": 12},
            "defer_destroy": {"closed_pending": 24, "closed_destroyed": 12},
        }
        for policy in get_args(ClosePolicy):
            with self.subTest(policy=policy):
                shapes = (compare(policy, case).shape for case in corpus)
                counts = Counter(shape.tag if shape else "source_rejected" for shape in shapes)
                self.assertEqual(counts, expected[policy])

    def test_guard_recovers_admission_when_opaque_call_left_no_dependency(self):
        case = next(
            case for case in fixtures()
            if case.proof.verdict == "UNKNOWN" and not case.statements and dict(case.proof.inputs)["refresh"]
        )
        self.assertIsNone(compare("source_proof", case).shape)
        result = compare("checked_snapshot", case).result
        self.assertEqual(result.calls, (CleanupCall("close", None, OK, True),))

    def test_stale_guard_keeps_the_connection_and_local_diagnostic(self):
        case = next(
            case for case in fixtures()
            if len(case.statements) == 1 and case.statements[0].failed_step
            and not dict(case.proof.inputs)["refresh"] and not dict(case.proof.inputs)["opaque_call"]
        )
        self.assertEqual(case.state.live_count, 0)
        result = compare("checked_snapshot", case)
        self.assertEqual(result.shape, ResultCase("stale_snapshot", frozenset({Obligation("handle", "retained")})))
        self.assertEqual(result.result.connection, "open")
        self.assertEqual(result.result.calls, (CleanupCall("finalize", "local", ERROR, False),))
        self.assertEqual(result.result.remaining_statements, ())

    def test_same_local_diagnostic_with_busy_pending_or_destroyed_connection(self):
        case = next(
            case for case in fixtures()
            if len(case.statements) == 3 and case.statements[-1].failed_step
            and dict(case.proof.inputs)["refresh"]
        )
        only_local = next(
            case for case in fixtures()
            if len(case.statements) == 1 and case.statements[0].failed_step
            and dict(case.proof.inputs)["refresh"]
        )
        expected_finalization = CleanupCall("finalize", "local", ERROR, False)
        busy = compare("recover_busy", case)
        pending = compare("defer_destroy", case)
        destroyed = compare("defer_destroy", only_local)
        self.assertEqual(busy.result.calls, (expected_finalization, CleanupCall("close", None, BUSY, False)))
        self.assertEqual(pending.result.calls, (expected_finalization, CleanupCall("close_v2", None, OK, False)))
        self.assertEqual(destroyed.result.calls, (expected_finalization, CleanupCall("close_v2", None, OK, True)))
        self.assertEqual(busy.result.remaining_statements, ("registered", "foreign"))
        self.assertEqual(pending.result.remaining_statements, ("registered", "foreign"))
        self.assertEqual(destroyed.result.remaining_statements, ())
        self.assertEqual(busy.shape, ResultCase("busy", frozenset({Obligation("handle", "retained")})))
        self.assertEqual(pending.shape, ResultCase("closed_pending"))
        self.assertEqual(destroyed.shape, ResultCase("closed_destroyed"))

    def test_forwarding_requires_an_arm_for_pending_and_a_handle_for_busy(self):
        corpus = tuple(fixtures())
        for policy in get_args(ClosePolicy):
            with self.subTest(policy=policy):
                returns = (compare(policy, case).shape for case in corpus)
                cases = frozenset(shape for shape in returns if shape is not None)
                arms = tuple(MatchArm(shape, tuple(item.slot for item in shape.obligations)) for shape in cases)
                self.assertFalse(check_result_arms(cases, arms, output="tagged_outcome"))
                self.assertEqual(check_result_arms(cases, arms, output="plain_result"), frozenset(
                    MatchIssue("ERROR_CANNOT_CARRY_OBLIGATIONS", shape) for shape in cases if shape.obligations
                ))
                arms_with_only_destroyed = (MatchArm(ResultCase("closed_destroyed"), ()),)
                self.assertEqual(check_result_arms(cases, arms_with_only_destroyed, output="tagged_outcome"), frozenset(
                    MatchIssue("MISSING_ARM", shape) for shape in cases if shape.tag != "closed_destroyed"
                ))
