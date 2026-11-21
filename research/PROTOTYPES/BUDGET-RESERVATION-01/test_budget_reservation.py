"""Bounded RT-26 model of cooperative admission for a cumulative budget."""

from dataclasses import dataclass, replace
from itertools import permutations
import unittest


@dataclass(frozen=True)
class Charge:
    task: str
    units: int
    state: str


class Budget:
    def __init__(self, parents: dict[str, str | None], limits: dict[str, int]):
        self.parents = parents
        self.limits = limits
        self.charges: dict[str, Charge] = {}
        self.used = dict.fromkeys(limits, 0)

    def ancestors(self, task):
        while task is not None:
            yield task
            task = self.parents[task]

    def reserve(self, operation, task, units):
        if type(units) is not int or units <= 0:
            raise ValueError("expected positive integer units")
        previous = self.charges.get(operation)
        if previous:
            if (previous.task, previous.units) != (task, units):
                raise ValueError("operation reused with different inputs")
            return previous.state

        scopes = tuple(self.ancestors(task))
        if any(self.used[scope] + units > self.limits[scope] for scope in scopes):
            self.charges[operation] = Charge(task, units, "denied")
            return "denied"
        for scope in scopes:
            self.used[scope] += units
        self.charges[operation] = Charge(task, units, "reserved")
        return "reserved"

    def settle(self, operation, *, commit):
        charge = self.charges.get(operation)
        if charge is None:
            return "unknown"
        if charge.state != "reserved":
            return charge.state
        if not commit:
            for scope in self.ancestors(charge.task):
                self.used[scope] -= charge.units
        state = "committed" if commit else "cancelled"
        self.charges[operation] = replace(charge, state=state)
        return state


def fixture():
    return Budget({"root": None, "group": "root", "a": "group", "b": "root"},
                  {"root": 5, "group": 5, "a": 4, "b": 5})


class BudgetReservationExperiment(unittest.TestCase):
    def test_split_check_then_charge_overshoots_in_four_of_six_interleavings(self):
        overshoots = 0
        schedules = 0
        for order in permutations("abAB"):
            if any(order.index(task) > order.index(task.upper()) for task in "ab"):
                continue
            schedules += 1
            used = 0
            admitted = {}
            for step in order:
                if step.islower():
                    admitted[step] = used + 3 <= 5
                elif admitted[step.lower()]:
                    used += 3
            overshoots += used > 5
        self.assertEqual((schedules, overshoots), (6, 4))

    def test_all_linearization_orders_match_an_independent_subtree_sum(self):
        events = (("reserve", "a"), ("reserve", "b"), ("commit", "a"),
                  ("cancel", "a"), ("commit", "b"), ("cancel", "b"))
        subtrees = {"root": {"a", "b"}, "group": {"a"}, "a": {"a"}, "b": {"b"}}
        transitions = 0
        for schedule in permutations(events):
            budget = fixture()
            for event, task in schedule:
                if event == "reserve":
                    budget.reserve(task, task, 3)
                else:
                    budget.settle(task, commit=event == "commit")
                live_or_spent = [charge for charge in budget.charges.values()
                                 if charge.state in {"reserved", "committed"}]
                for scope, descendants in subtrees.items():
                    expected = sum(charge.units for charge in live_or_spent if charge.task in descendants)
                    self.assertEqual(budget.used[scope], expected)
                    self.assertLessEqual(expected, budget.limits[scope])
                transitions += 1
        self.assertEqual(transitions, 4320)

    def test_retry_and_late_cancellation_do_not_create_or_refund_spent_units(self):
        budget = fixture()
        self.assertEqual(budget.reserve("charge", "a", 3), "reserved")
        self.assertEqual(budget.reserve("charge", "a", 3), "reserved")
        with self.assertRaisesRegex(ValueError, "different inputs"):
            budget.reserve("charge", "b", 3)
        self.assertEqual(budget.settle("charge", commit=True), "committed")
        self.assertEqual(budget.settle("charge", commit=False), "committed")
        self.assertEqual(budget.used, {"root": 3, "group": 3, "a": 3, "b": 0})
        self.assertEqual(budget.reserve("other", "b", 3), "denied")

    def test_cancellation_releases_pending_units_and_denied_retry_is_stable(self):
        budget = fixture()
        self.assertEqual(budget.reserve("over-leaf", "a", 5), "denied")
        self.assertEqual(budget.reserve("pending", "a", 4), "reserved")
        self.assertEqual(budget.reserve("blocked", "b", 3), "denied")
        self.assertEqual(budget.settle("pending", commit=False), "cancelled")
        self.assertEqual(budget.settle("pending", commit=False), "cancelled")
        self.assertEqual(budget.reserve("blocked", "b", 3), "denied")
        self.assertEqual(budget.reserve("fresh", "b", 3), "reserved")
        self.assertEqual(budget.used, {"root": 3, "group": 0, "a": 0, "b": 3})
