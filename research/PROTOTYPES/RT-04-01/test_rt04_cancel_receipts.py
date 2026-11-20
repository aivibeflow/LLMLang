"""Check cancellation signaling, result identity, and late delivery."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from itertools import permutations, product
from threading import Event
from typing import get_args
from unittest import TestCase

from rt04_backup_roles import BackupPair
from rt04_cancel_receipts import Evidence, Invocation, Kind, Policy, Reservation, admits, apply


def compatible(left, right, live):
    source, destination = left
    next_source, next_destination = right
    return next_source != next_destination and not (live and (destination in right or source == next_destination))


class CancellationReceiptTests(TestCase):
    def test_acknowledgement_is_observed_while_worker_is_still_live(self):
        subject = Invocation(BackupPair("a", "b"), 1)
        state = Reservation(subject)
        requested = Event()
        acknowledged = Event()
        may_finish = Event()

        def worker():
            if not requested.wait(timeout=5):
                raise RuntimeError("cancel request was not received")
            acknowledged.set()
            if not may_finish.wait(timeout=5):
                raise RuntimeError("fixture did not allow cleanup to finish")
            return Evidence(subject, "consumed")

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(worker)
            blocker = BackupPair("c", "b")
            try:
                requested.set()
                self.assertTrue(acknowledged.wait(timeout=5))
                self.assertFalse(future.done())
                ack = Evidence(subject, "acknowledged")
                self.assertTrue(admits(apply("ack_by_invocation", state, ack), blocker))
                state = apply("terminal_by_invocation", state, ack)
                self.assertFalse(admits(state, blocker))
            finally:
                may_finish.set()
            completion = future.result(timeout=5)
        self.assertTrue(admits(apply("terminal_by_invocation", state, completion), blocker))

    def test_late_completion_does_not_release_a_new_invocation_with_the_same_roles(self):
        pair = BackupPair("a", "b")
        original = Invocation(pair, 1)
        successor = Invocation(pair, 2)
        completion = Evidence(original, "consumed")
        finished = apply("terminal_by_invocation", Reservation(original), completion)
        self.assertEqual(finished.phase, "released")
        current = Reservation(successor)
        self.assertEqual(apply("terminal_by_roles", current, completion).phase, "released")
        self.assertEqual(apply("terminal_by_invocation", current, completion), current)

    def test_released_record_is_stable_under_repeated_and_out_of_order_delivery(self):
        subject = Invocation(BackupPair("a", "b"), 1)
        state = Reservation(subject, "retained")
        completion = Evidence(subject, "consumed")
        finished = apply("terminal_by_invocation", state, completion)
        for kind in get_args(Kind):
            with self.subTest(kind=kind):
                self.assertEqual(apply("terminal_by_invocation", finished, Evidence(subject, kind)), finished)

    def test_unresolved_evidence_retains_compatible_shared_roles(self):
        subject = Invocation(BackupPair("a", "b"), 7)
        state = Reservation(subject)
        for kind in ("acknowledged", "not_found", "unresolved"):
            with self.subTest(kind=kind):
                unchanged = apply("terminal_by_invocation", state, Evidence(subject, kind))
                self.assertEqual(unchanged, state)
                self.assertTrue(admits(unchanged, BackupPair("a", "c")))
                self.assertFalse(admits(unchanged, BackupPair("c", "b")))

    def test_all_evidence_subjects_and_dispositions(self):
        expected = {
            "ack_by_invocation": (1632, 96, 1152, 192, 0),
            "terminal_by_roles": (1632, 96, 1152, 192, 384),
            "terminal_by_invocation": (1440, 0, 1248, 0, 0),
        }
        for policy in get_args(Policy):
            with self.subTest(policy=policy):
                counts = Counter()
                for left, right in product(permutations("abcd", 2), product("abcd", repeat=2)):
                    roles = BackupPair(*left)
                    current = Invocation(roles, 2)
                    previous = Invocation(roles, 1)
                    other = Invocation(BackupPair(left[1], left[0]), 2)
                    for subject, kind, live in product((current, previous, other), get_args(Kind), (True, False)):
                        if subject == current and ((kind == "consumed" and live) or (kind == "retained" and not live)):
                            continue
                        result = apply(policy, Reservation(current), Evidence(subject, kind))
                        allowed = admits(result, BackupPair(*right))
                        oracle = compatible(left, right, live)
                        counts["inputs"] += 1
                        counts["admitted"] += allowed
                        counts["unsafe_admission"] += allowed and not oracle
                        counts["extra_refusal"] += not allowed and oracle
                        counts["premature_release"] += live and result.phase == "released"
                        counts["unsupported_handle"] += subject != current and result.phase == "retained"
                self.assertEqual(counts["inputs"], 5376)
                columns = ("admitted", "unsafe_admission", "extra_refusal", "premature_release", "unsupported_handle")
                self.assertEqual(tuple(counts[key] for key in columns), expected[policy])
