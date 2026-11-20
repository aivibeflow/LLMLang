"""Cross-check source-derived roles against independently specified finite inputs."""

from collections import Counter
from itertools import product
from unittest import TestCase

from rt04_backup_roles import BackupPair
from rt04_backup_source_roles import Observation, Route, UnsupportedSource, observe, parse, routes, widen


_TERMS = (
    ("a", lambda p, q, external: "a"),
    ("b", lambda p, q, external: "b"),
    ("c", lambda p, q, external: "c"),
    ("external", lambda p, q, external: external),
    ("a if p else b", lambda p, q, external: "a" if p else "b"),
    ("b if p else a", lambda p, q, external: "b" if p else "a"),
    ("a if q else b", lambda p, q, external: "a" if q else "b"),
    ("c if p else external", lambda p, q, external: "c" if p else external),
)
_FINISHES = (
    ("", lambda p: True),
    ("if p:\n    finish_first()\n", lambda p: not p),
    ("finish_first()\n", lambda p: False),
)
_INPUTS = tuple(product((False, True), (False, True), ("a", "b", "c")))


def oracle(first_source, first_destination, next_source, next_destination, retains):
    """Independent role checks on the generator's concrete identities."""
    first = BackupPair(first_source, first_destination)
    second = BackupPair(next_source, next_destination)
    if first_source == first_destination:
        return Observation("first_refused", ())
    live = (first,) if retains else ()
    conflict = retains and (
        first_destination in (next_source, next_destination) or first_source == next_destination
    )
    if next_source == next_destination or conflict:
        return Observation("second_refused", live)
    return Observation("started", (*live, second))


def relation(source):
    return frozenset(routes(parse(source)))


def results(view):
    return {observe(route).result for route in view}


class SourceRoleTests(TestCase):
    def test_roles_inside_one_call_can_be_correlated(self):
        view = relation("backup(a if p else b, b if p else a)\nfinish_first()\nbackup(a, c)")
        self.assertIn("first_refused", results(widen(view, "role_sets")))
        self.assertEqual(results(widen(view, "call_pairs")), {"started"})

    def test_both_calls_can_depend_on_the_same_flag(self):
        view = relation("backup(a if p else b, b if p else a)\nbackup(a if p else b, c)")
        self.assertIn("second_refused", results(widen(view, "call_pairs")))
        self.assertEqual(results(view), {"started"})

    def test_finish_can_be_correlated_with_the_second_destination(self):
        view = relation("backup(a, b)\nif p:\n    finish_first()\nbackup(a, b if p else c)")
        self.assertEqual(results(widen(view, "call_pairs")), {"started"})
        self.assertIn("second_refused", results(widen(view, "role_sets")))

    def test_rebinding_a_local_name_preserves_the_original_reservation(self):
        view = relation("destination = b\nbackup(a, destination)\ndestination = c\nbackup(a, b)")
        self.assertEqual({observe(route) for route in view}, {Observation("second_refused", (BackupPair("a", "b"),))})

    def test_input_identity_can_refuse_second_call_with_first_still_live(self):
        view = relation("backup(a, b)\nbackup(external, c)")
        self.assertEqual({observe(route) for route in view}, {
            Observation("started", (BackupPair("a", "b"), BackupPair("a", "c"))),
            Observation("second_refused", (BackupPair("a", "b"),)),
        })

    def test_unsupported_source_fails_closed(self):
        malformed = (
            "backup(a, b)\nbackup(a, missing)",
            "backup(a, b)\nif a:\n    finish_first()\nbackup(a, c)",
            "backup(a, b)\nfinish_first()\nfinish_first()\nbackup(a, c)",
            "a = b\nbackup(a, b)\nbackup(a, c)",
            "backup(a, b)\nbackup(a, c)\nbackup(b, c)",
            "backup(a, b)\nunknown(a)\nbackup(a, c)",
        )
        for source in malformed:
            with self.subTest(source=source):
                with self.assertRaises(UnsupportedSource):
                    parse(source)

    def test_all_generated_programs(self):
        runtime = Counter()
        proofs = Counter()
        for (a, eval_a), (b, eval_b), (c, eval_c), (d, eval_d) in product(_TERMS, repeat=4):
            for finish, eval_retains in _FINISHES:
                source = f"backup({a}, {b})\n{finish}backup({c}, {d})\n"
                exact = set()
                for concrete, inputs in zip(routes(parse(source)), _INPUTS, strict=True):
                    first = BackupPair(eval_a(*inputs), eval_b(*inputs))
                    second = BackupPair(eval_c(*inputs), eval_d(*inputs))
                    retains = eval_retains(inputs[0])
                    self.assertEqual(concrete, Route(first, second, retains), source)
                    expected = oracle(first.source, first.destination, second.source, second.destination, retains)
                    self.assertEqual(observe(concrete), expected, source)
                    runtime[expected.result] += 1
                    exact.add(concrete)
                view = frozenset(exact)
                pairs = widen(view, "call_pairs")
                roles = widen(view, "role_sets")
                self.assertTrue(view <= pairs <= roles, source)
                for name, subset in (("role_sets", roles), ("call_pairs", pairs), ("full_route", view)):
                    proofs[name] += int(results(subset) == {"started"})

        self.assertEqual(runtime, {"first_refused": 56064, "second_refused": 57928, "started": 33464})
        self.assertEqual(proofs, {"role_sets": 156, "call_pairs": 214, "full_route": 232})
