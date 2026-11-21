"""Enumerate delivery orders for overlapping diagnostic analysis requests."""

from collections import Counter
from dataclasses import dataclass
from itertools import permutations
import unittest

from test_diagnostic_replay import snapshot


ENTRY = "entry"
PROVIDER = "provider"
OVERRIDE = "local-provider"
CONFIG = "config"


def evaluate(files):
    """Fixture checker. A missing override affects selection of the provider."""
    if files[ENTRY] != b"call":
        return ("PARSE",)
    selected = files.get(OVERRIDE, files[PROVIDER])
    if selected != files[CONFIG]:
        return ("TYPE",)
    return ()


def projection(files):
    return tuple((path, files.get(path)) for path in (ENTRY, PROVIDER, OVERRIDE, CONFIG))


def key(files, policy):
    if policy == "document":
        return files[ENTRY]
    if policy == "workspace":
        return snapshot(files)
    if policy == "projection":
        return projection(files)
    raise ValueError(f"unknown policy: {policy}")


@dataclass(frozen=True)
class Result:
    request: int
    observed: object
    diagnostics: tuple[str, ...]
    complete: bool


class Publisher:
    def __init__(self, files, policy):
        self.files = dict(files)
        self.policy = policy
        self.latest = None
        self.cancelled = set()
        self.visible = None

    def change(self, edits):
        self.files.update(edits)
        if self.visible is not None and self.visible.observed != key(self.files, self.policy):
            self.visible = None

    def start(self, request):
        self.latest = request
        # Work executes later but reads this immutable fixture snapshot.
        return Result(request, key(self.files, self.policy), evaluate(self.files), True)

    def cancel(self, request):
        self.cancelled.add(request)

    def deliver(self, result):
        if (result.complete and result.request == self.latest
                and result.request not in self.cancelled
                and result.observed == key(self.files, self.policy)):
            self.visible = result
            return True
        return False


BASE = {ENTRY: b"call", PROVIDER: b"int", CONFIG: b"int", "notes": b"initial"}
EDITS = {
    "entry": {ENTRY: b"broken"},
    "dependency": {PROVIDER: b"bool"},
    "formerly-absent-override": {OVERRIDE: b"bool"},
    "configuration": {CONFIG: b"bool"},
    "unrelated": {"notes": b"edited"},
}


def schedules():
    for seq in permutations(("edit", "new", "cancel", "old-result", "new-result")):
        # Both requests return, even if they receive cancellation.
        if seq.index("edit") < seq.index("new") < min(seq.index("cancel"), seq.index("new-result")):
            yield seq


def replay(policy, edits, sequence):
    publisher = Publisher(BASE, policy)
    requests = {1: publisher.start(1)}
    running = 1
    cancelled = False
    oracle_visible = None
    counts = Counter()
    for event in sequence:
        if event == "edit":
            publisher.change(edits)
            if evaluate(BASE) != evaluate({**BASE, **edits}):
                oracle_visible = None
        elif event == "new":
            running = 2
            requests[2] = publisher.start(2)
        elif event == "cancel":
            cancelled = True
            publisher.cancel(2)
        else:
            request = 1 if event == "old-result" else 2
            result = requests[request]
            current = evaluate(publisher.files)
            accept = (request == running and not (request == 2 and cancelled)
                      and result.diagnostics == current)
            if accept:
                oracle_visible = current
            published = publisher.deliver(result)
            counts["unsafe-publications"] += published and not accept
            counts["unnecessary-rejections"] += accept and not published
        actual = publisher.visible.diagnostics if publisher.visible is not None else None
        counts["visible-disagreements"] += actual != oracle_visible
    return counts


class DiagnosticPublication(unittest.TestCase):
    def test_all_delivery_orders_and_edits(self):
        orders = tuple(schedules())
        self.assertEqual(len(orders), 10)
        totals = {}
        for policy in ("document", "workspace", "projection"):
            result = Counter()
            for edit in EDITS.values():
                for order in orders:
                    result.update(replay(policy, edit, order))
            totals[policy] = dict(result)
        self.assertEqual(totals, {
            "document": {"unsafe-publications": 6, "unnecessary-rejections": 0,
                         "visible-disagreements": 36},
            "workspace": {"unsafe-publications": 0, "unnecessary-rejections": 2,
                          "visible-disagreements": 12},
            "projection": {"unsafe-publications": 0, "unnecessary-rejections": 0,
                           "visible-disagreements": 0},
        })

    def test_cancelled_or_partial_empty_result_cannot_clear_an_error(self):
        publisher = Publisher({**BASE, **EDITS["dependency"]}, "projection")
        previous = publisher.start(1)
        self.assertTrue(publisher.deliver(previous))
        current = publisher.start(2)
        self.assertFalse(publisher.deliver(Result(2, current.observed, (), False)))
        publisher.cancel(2)
        self.assertFalse(publisher.deliver(current))
        self.assertIs(publisher.visible, previous)
        publisher.change({PROVIDER: b"int"})
        self.assertIsNone(publisher.visible)
        self.assertTrue(publisher.deliver(publisher.start(3)))
        self.assertEqual(publisher.visible.diagnostics, ())


if __name__ == "__main__":
    unittest.main()
