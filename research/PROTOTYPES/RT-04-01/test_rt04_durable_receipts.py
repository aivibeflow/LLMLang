"""Check receipt recovery in a model and with abrupt SQLite process exits."""

from itertools import product
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import get_args
from unittest import TestCase

from rt04_backup_roles import BackupPair
from rt04_cancel_receipts import Evidence, Invocation, Reservation, admits
from rt04_durable_receipts import Cut, Publication, RecoveryView, predict, recover
from sqlite_durable_receipts_probe import probe


class DurableReceiptTests(TestCase):
    def test_crash_boundaries(self):
        pending = RecoveryView(True, False, False)
        lost_record = RecoveryView(False, False, False)
        lost_reply = RecoveryView(False, True, False)
        delivered = RecoveryView(False, True, True)
        labels = ("before_effect", "after_effect", "after_record", "after_commit", "complete")
        self.assertEqual(tuple(predict("atomic", label) for label in labels), (
            pending, pending, pending, lost_reply, delivered,
        ))
        self.assertEqual(tuple(predict("separate", label) for label in labels), (
            pending, lost_record, lost_record, lost_reply, delivered,
        ))

    def test_absent_terminal_result_preserves_bounded_roles(self):
        roles = BackupPair("a", "b")
        current = Reservation(Invocation(roles, 1))
        recovered = recover(current, None)
        self.assertEqual(recovered, current)
        self.assertFalse(admits(recovered, roles))
        self.assertTrue(admits(recovered, BackupPair("a", "c")))

    def test_reset_counter_can_make_old_evidence_look_current(self):
        roles = BackupPair("a", "b")
        previous = Invocation(roles, 1)
        stale = Evidence(previous, "consumed")
        reused_key = Reservation(Invocation(roles, 1))
        newer = Reservation(Invocation(roles, 2))
        self.assertTrue(admits(recover(reused_key, stale), roles))
        self.assertFalse(admits(recover(newer, stale), roles))

    def test_fresh_processes_match_every_crash_boundary(self):
        with TemporaryDirectory(prefix="llmlang-receipts-test-") as directory:
            for publication, cut in product(get_args(Publication), get_args(Cut)):
                with self.subTest(publication=publication, cut=cut):
                    path = Path(directory) / f"{publication}-{cut}.sqlite"
                    self.assertEqual(probe(path, publication, cut), predict(publication, cut))
