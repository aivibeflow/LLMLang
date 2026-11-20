"""Check typed recovery against the independently evaluated call trace."""

from collections import Counter
from dataclasses import replace
from itertools import product
from typing import get_args
from unittest import TestCase

from rt04_backup_roles import BackupPair
from rt04_owned_call_match import Obligation
from rt04_return_disposition import Disposition, TransferTiming
from rt04_shared_owned_handlers import CallerTrace, PRESERVE_SOURCE, RECOVER_SOURCE, compile_caller, execute
from rt04_shared_owned_transitions import execute as transition_execute
from rt04_shared_owned_workload import Inputs


def oracle(workload, timing, inputs, disposition, *, recover):
    original = transition_execute(workload, timing, inputs)
    if original.result is None:
        return CallerTrace(original, frozenset())

    original_moves = original.result.obligations
    kinds = {item.slot: item.kind for item in original_moves}
    if original.result.tag == "OkWithValue":
        arm = "success"
    else:
        arm = {None: "error_without_handle", "owned": "error_with_handle", "retained": "error_with_handle",
               "reconcile": "error_reconcile"}[kinds.get("handle")]
    action = "release_first" if recover and arm == "error_with_handle" else "preserve"
    prefix_count = 2 if original.second == "started" else 1
    events = (*original.events[:-prefix_count], ("match", arm, action))
    errors = original.cleanup_errors
    prior = tuple(entry for entry in original.reservations if entry[0] == "handle")
    if action == "release_first":
        remaining = {item for item in original_moves if item.slot == "local"}
        if disposition in ("ok", "consumed_error"):
            prior = ()
        else:
            state = "retained" if disposition == "retained_error" else "reconcile"
            remaining.add(Obligation("handle", state))
        original_moves = frozenset(remaining)
        events += (("release", "caller_handle", disposition),)
        if disposition != "ok":
            errors += (("caller_handle", disposition),)

    values = dict(zip("abcd", inputs.identities, strict=True))
    source = values[workload.second.source]
    destination = values[workload.second.destination]
    conflict = any(pair.destination in (source, destination) or pair.source == destination for _, pair in prior)
    if source == destination or conflict:
        updated = replace(original, second="refused", reservations=prior,
                          events=(*events, ("check", "second", "refused")), cleanup_errors=errors)
    else:
        updated = replace(original, second="started", reservations=(*prior, ("second", BackupPair(source, destination))),
                          events=(*events, ("check", "second", "ok"), ("acquire", "second", "ok")), cleanup_errors=errors)
    return CallerTrace(updated, original_moves)


class OwnedHandlerTests(TestCase):
    def test_match_is_exhaustive_and_requires_release_authority(self):
        for timing in get_args(TransferTiming):
            for arm in ("error_reconcile", "error_without_handle"):
                with self.subTest(timing=timing, arm=arm):
                    initial = f'case "{arm}":\n        preserve()'
                    invalid = RECOVER_SOURCE.replace(initial, f'case "{arm}":\n        release_first()')
                    with self.assertRaisesRegex(ValueError, "requires a usable handle"):
                        compile_caller(invalid, timing)
            missing = RECOVER_SOURCE.replace('    case "error_reconcile":\n        preserve()\n', "")
            with self.assertRaisesRegex(ValueError, "one arm for each inferred result group"):
                compile_caller(missing, timing)

    def test_consuming_release_error_allows_reuse_and_preserves_local_obligation(self):
        caller = compile_caller(RECOVER_SOURCE, "before_cleanup")
        inputs = Inputs(("a", "b", "c", "b"), True, "retained_error", "ok")
        trace = execute(caller, inputs, "consumed_error")
        self.assertEqual(trace.trace.second, "started")
        self.assertEqual(trace.forwarded, {Obligation("local", "retained")})
        self.assertEqual(trace.trace.cleanup_errors, (("local", "retained_error"), ("caller_handle", "consumed_error")))
        self.assertEqual(trace.trace.reservations, (("second", BackupPair("c", "b")),))

    def test_unknown_handle_stays_unresolved_and_never_enters_the_release_arm(self):
        caller = compile_caller(RECOVER_SOURCE, "after_cleanup")
        inputs = Inputs(("a", "b", "c", "b"), True, "consumed_error", "indeterminate")
        trace = execute(caller, inputs, "ok")
        self.assertEqual(trace.trace.second, "refused")
        self.assertEqual(trace.forwarded, {Obligation("handle", "reconcile")})
        self.assertIn(("match", "error_reconcile", "preserve"), trace.trace.events)
        self.assertNotIn(("release", "caller_handle", "ok"), trace.trace.events)

    def test_all_caller_paths(self):
        expected = {
            "before_cleanup": (1728, 2688, 3456, 384, 2592, 480),
            "after_cleanup": (2448, 2868, 1512, 168, 1134, 210),
        }
        for timing in get_args(TransferTiming):
            with self.subTest(timing=timing):
                baseline = compile_caller(PRESERVE_SOURCE, timing)
                changed = compile_caller(RECOVER_SOURCE, timing)
                counts = Counter()
                for ids, wants, local, handle, released in product(
                    product("abc", repeat=4), (False, True), get_args(Disposition), get_args(Disposition), get_args(Disposition),
                ):
                    inputs = Inputs(ids, wants, local, handle)
                    initial = execute(baseline, inputs, released)
                    result = execute(changed, inputs, released)
                    self.assertEqual(initial, oracle(baseline.workload, timing, inputs, released, recover=False))
                    self.assertEqual(result, oracle(changed.workload, timing, inputs, released, recover=True))
                    admitted_before = initial.trace.second == "started"
                    admitted_after = result.trace.second == "started"
                    attempted = ("release", "caller_handle", released) in result.trace.events
                    self.assertTrue(not admitted_before or admitted_after)
                    counts["inputs"] += 1
                    counts["baseline"] += admitted_before
                    counts["recovery"] += admitted_after
                    counts["attempted"] += attempted
                    counts["already_admitted"] += attempted and admitted_before
                    counts["diagnostics"] += attempted and released != "ok"
                    counts["consumed_error"] += not admitted_before and admitted_after and released == "consumed_error"
                self.assertEqual(counts["inputs"], 10368)
                columns = ("baseline", "recovery", "attempted", "already_admitted", "diagnostics", "consumed_error")
                self.assertEqual(tuple(counts[key] for key in columns), expected[timing])
