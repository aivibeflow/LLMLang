"""Separate closing admissions from settling the work that already owns a reservation."""

from collections import Counter
from dataclasses import dataclass, field
from itertools import permutations
import unittest


LIMIT = 5
AMOUNT = 3
PARENT = {"nested": "group", "sibling": "root", "group": "root", "root": None}
EVENTS = ("admit-nested", "cancel-group", "ack", "spend", "settle", "admit-sibling")


def within(task, scope):
    while task is not None:
        if task == scope:
            return True
        task = PARENT[task]
    return False


@dataclass
class Ledger:
    policy: str
    closed: set[str] = field(default_factory=set)
    records: dict[str, str] = field(default_factory=dict)
    spent: set[str] = field(default_factory=set)
    actual_reservations: set[str] = field(default_factory=set)

    def used(self):
        return AMOUNT * sum(status in ("reserved", "committed") for status in self.records.values())

    def admit(self, task):
        if task in self.records:
            return False
        if self.policy != "ack-only" and any(within(task, scope) for scope in self.closed):
            return False
        if self.used() + AMOUNT > LIMIT:
            return False
        self.records[task] = "reserved"
        self.actual_reservations.add(task)
        return True

    def apply(self, event):
        match event:
            case "admit-nested":
                return self.admit("nested")
            case "admit-sibling":
                return self.admit("sibling")
            case "cancel-group":
                self.closed.add("group")
            case "ack":
                if self.policy in ("ack-only", "refund-on-ack"):
                    if self.records.get("nested") == "reserved":
                        self.records["nested"] = "released"
            case "spend":
                if "nested" in self.actual_reservations:
                    self.spent.add("nested")
            case "settle":
                if "nested" in self.actual_reservations:
                    self.actual_reservations.remove("nested")
                    self.records["nested"] = "committed" if "nested" in self.spent else "released"
            case _:
                raise ValueError(event)
        return False


def schedules():
    for schedule in permutations(EVENTS):
        if (schedule.index("cancel-group") < schedule.index("ack")
                and schedule.index("admit-nested") < schedule.index("spend") < schedule.index("settle")):
            yield schedule


def count_outcomes(policy, cases, spend):
    totals = Counter()
    for schedule in cases:
        model = Ledger(policy)
        late_admission = overdraft = undercharge = False
        for event in schedule:
            admitted = False if event == "spend" and not spend else model.apply(event)
            actual = AMOUNT * len(model.actual_reservations | model.spent)
            late_admission |= (event == "admit-nested" and admitted and "group" in model.closed)
            overdraft |= actual > LIMIT
            undercharge |= model.used() < actual
        totals["late-admission"] += late_admission
        totals["overshoot"] += overdraft
        totals["undercharge"] += undercharge
    return dict(totals)


class CancellationAccounting(unittest.TestCase):
    def test_all_valid_orders(self):
        cases = tuple(schedules())
        self.assertEqual(len(cases), 60)
        expected = {
            "ack-only": {"late-admission": 15, "overshoot": 7, "undercharge": 23},
            "refund-on-ack": {"late-admission": 0, "overshoot": 4, "undercharge": 15},
            "terminal": {"late-admission": 0, "overshoot": 0, "undercharge": 0},
        }
        for policy, spend in ((policy, spend) for policy in expected for spend in (False, True)):
            with self.subTest(policy=policy, spend=spend):
                self.assertEqual(count_outcomes(policy, cases, spend), expected[policy])

    def test_cancel_before_admission_does_not_close_sibling(self):
        ledger = Ledger("terminal")
        ledger.apply("cancel-group")
        ledger.apply("ack")
        self.assertFalse(ledger.admit("nested"))
        self.assertTrue(ledger.admit("sibling"))
        self.assertEqual(ledger.used(), AMOUNT)

    def test_terminal_stop_can_release_unused_reservation_but_never_spent_amount(self):
        for used in (False, True):
            with self.subTest(used=used):
                ledger = Ledger("terminal")
                self.assertTrue(ledger.admit("nested"))
                ledger.apply("cancel-group")
                ledger.apply("ack")
                self.assertFalse(ledger.admit("sibling"))
                if used:
                    ledger.apply("spend")
                ledger.apply("settle")
                ledger.apply("settle")
                self.assertEqual(ledger.used(), AMOUNT if used else 0)
                self.assertEqual(ledger.admit("sibling"), not used)


if __name__ == "__main__":
    unittest.main()
