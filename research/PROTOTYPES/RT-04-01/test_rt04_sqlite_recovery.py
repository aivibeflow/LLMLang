import unittest
from collections import Counter
from itertools import product
from typing import get_args

from rt04_sqlite_recovery import BUSY, ERROR, OK, CleanupCall, Policy, Statement, cleanup, statement_fixtures


class SQLiteRecoveryExperiment(unittest.TestCase):
    def test_precondition_checks_the_live_set_at_close(self):
        statements = (Statement("local", True, False),)
        early = cleanup("require_empty", statements, close_first=True)
        self.assertFalse(early.accepted)
        self.assertEqual(early.calls, ())
        self.assertEqual(early.remaining_statements, ("local",))

        after = cleanup("require_empty", statements, close_first=False)
        self.assertTrue(after.accepted)
        self.assertEqual(after.calls, (
            CleanupCall("finalize", "local", OK, False), CleanupCall("close", None, OK, True),
        ))

    def test_busy_retry_runs_after_finalization_even_when_finalization_reports_an_error(self):
        statements = (Statement("one", True, True), Statement("two", True, True))
        result = cleanup("recover_busy", statements, close_first=True)
        self.assertEqual(result.connection, "destroyed")
        self.assertEqual(result.calls, (
            CleanupCall("close", None, BUSY, False), CleanupCall("finalize", "one", ERROR, False),
            CleanupCall("finalize", "two", ERROR, False), CleanupCall("close", None, OK, True),
        ))
        self.assertEqual(result.finalize_errors, ("one", "two"))
        self.assertFalse(result.forwards_connection)

    def test_busy_forwards_the_open_connection_if_an_external_statement_remains(self):
        statements = (Statement("local", True, False), Statement("outside", False, True))
        result = cleanup("recover_busy", statements, close_first=True)
        self.assertTrue(result.forwards_connection)
        self.assertEqual(result.remaining_statements, ("outside",))
        self.assertEqual(result.calls, (
            CleanupCall("close", None, BUSY, False), CleanupCall("finalize", "local", OK, False),
        ))

    def test_deferred_close_consumes_the_connection_capability_with_external_work_pending(self):
        statements = (Statement("local", True, True), Statement("outside", False, False))
        result = cleanup("defer_destroy", statements, close_first=True)
        self.assertEqual(result.connection, "pending")
        self.assertFalse(result.forwards_connection)
        self.assertEqual(result.remaining_statements, ("outside",))
        self.assertEqual(result.calls, (
            CleanupCall("close_v2", None, OK, False), CleanupCall("finalize", "local", ERROR, False),
        ))

    def test_last_dependent_is_consumed_and_triggers_destruction_on_error(self):
        result = cleanup("defer_destroy", (Statement("last", True, True),), close_first=True)
        self.assertEqual(result.connection, "destroyed")
        self.assertEqual(result.calls, (
            CleanupCall("close_v2", None, OK, False), CleanupCall("finalize", "last", ERROR, True),
        ))
        self.assertEqual(result.finalize_errors, ("last",))

    def test_all_initial_graphs_preserve_external_ownership_and_ordered_diagnostics(self):
        accepted = Counter()
        busy = Counter()
        forwarded = Counter()
        pending = Counter()
        cases = 0
        for statements, policy, close_first in product(statement_fixtures(), get_args(Policy), (True, False)):
            cases += 1
            result = cleanup(policy, statements, close_first=close_first)
            local = tuple(s.name for s in statements if s.owned_here)
            outside = tuple(s.name for s in statements if not s.owned_here)
            with self.subTest(statements=statements, policy=policy, close_first=close_first):
                if not result.accepted:
                    self.assertEqual(policy, "require_empty")
                    self.assertEqual(result.calls, ())
                    self.assertEqual(result.remaining_statements, tuple(s.name for s in statements))
                    continue
                accepted[policy, close_first] += 1
                busy[policy, close_first] += any(call.code == BUSY for call in result.calls)
                forwarded[policy, close_first] += result.forwards_connection
                pending[policy, close_first] += result.connection == "pending"
                self.assertEqual(result.remaining_statements, outside)
                self.assertEqual(tuple(c.statement for c in result.calls if c.operation == "finalize"), local)
                self.assertEqual(result.finalize_errors, tuple(s.name for s in statements if s.owned_here and s.failed_step))
                self.assertEqual(tuple(c.destroyed for c in result.calls[:-1]), (False,) * (len(result.calls) - 1))
                self.assertEqual(result.calls[-1].destroyed, not outside)

        self.assertEqual(cases, 510)
        self.assertEqual(accepted["require_empty", True], 1)
        self.assertEqual(accepted["require_empty", False], 15)
        self.assertEqual(sum(accepted.values()), 356)
        self.assertEqual((busy["recover_busy", True], busy["recover_busy", False]), (84, 70))
        self.assertEqual((forwarded["recover_busy", True], forwarded["recover_busy", False]), (70, 70))
        self.assertEqual((pending["defer_destroy", True], pending["defer_destroy", False]), (70, 70))

    def test_require_empty_rejects_without_local_cleanup_when_a_dependency_is_external(self):
        result = cleanup("require_empty", (
            Statement("local", True, False), Statement("outside", False, False),
        ), close_first=False)
        self.assertFalse(result.accepted)
        self.assertEqual(result.calls, ())
        self.assertEqual(result.remaining_statements, ("local", "outside"))

    def test_duplicate_statement_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "must be unique"):
            cleanup("defer_destroy", (Statement("s", True, False), Statement("s", False, True)), close_first=True)


if __name__ == "__main__":
    unittest.main()
