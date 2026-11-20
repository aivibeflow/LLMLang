import unittest
from collections import Counter
from itertools import product
from textwrap import indent

from rt04_close_evidence import UnsupportedSource, analyze, executions, parse


def fixture_sources():
    choices = (
        "pass",
        "readonly(db)",
        "foreign(db)",
        "{name} = prepare(db)",
        "{name} = prepare(db)\nfinalize({name})",
        "inspect(db)",
    )
    for parts in product(choices, repeat=4):
        before, yes, no, after = (part.format(name=f"s{i}") for i, part in enumerate(parts))
        yield "\n".join((
            "db = connect()", before, "inspect(db)",
            "if choose:", indent(yes, "    "), "else:", indent(no, "    "),
            after, "close(db)",
        ))


def approvals(fact, run):
    return {
        "local_only": not fact.known_live,
        "source_proof": fact.verdict == "PROVEN_EMPTY",
        "unchecked_snapshot": run.unchecked_snapshot_allows_close,
        "current_snapshot": run.current_snapshot_allows_close,
        "immediate_check": not run.would_be_busy,
    }


class CloseEvidenceExperiment(unittest.TestCase):
    def test_preserved_effect_preserves_complete_and_current_evidence(self):
        p = parse("db = connect()\ninspect(db)\nreadonly(db)\nclose(db)")
        self.assertEqual(analyze(p)[0].verdict, "PROVEN_EMPTY")
        run, = executions(p)
        self.assertTrue(run.current_snapshot_allows_close)
        self.assertFalse(run.would_be_busy)

    def test_opaque_call_can_make_an_empty_snapshot_unsound(self):
        p = parse("db = connect()\ninspect(db)\nforeign(db)\nclose(db)")
        self.assertEqual(analyze(p)[0].verdict, "UNKNOWN")
        runs = tuple(executions(p))
        self.assertEqual({r.would_be_busy for r in runs}, {False, True})
        self.assertTrue(all(r.unchecked_snapshot_allows_close for r in runs))
        self.assertFalse(any(r.current_snapshot_allows_close for r in runs))

    def test_actual_reinspection_can_discharge_uncertainty(self):
        p = parse("db = connect()\nforeign(db)\ninspect(db)\nclose(db)")
        self.assertEqual(analyze(p)[0].verdict, "UNKNOWN")
        self.assertEqual({(r.current_snapshot_allows_close, r.would_be_busy) for r in executions(p)}, {
            (True, False), (False, True),
        })

    def test_restoring_the_empty_set_does_not_restore_the_version(self):
        p = parse("db = connect()\ninspect(db)\ns = prepare(db)\nfinalize(s)\nclose(db)")
        self.assertEqual(analyze(p)[0].verdict, "PROVEN_EMPTY")
        run, = executions(p)
        self.assertFalse(run.would_be_busy)
        self.assertTrue(run.unchecked_snapshot_allows_close)
        self.assertFalse(run.current_snapshot_allows_close)

    def test_immutable_input_correlates_creation_with_finalization(self):
        p = parse("db = connect()\nif flag:\n    q = prepare(db)\nif flag:\n    finalize(q)\nclose(db)")
        facts = analyze(p)
        self.assertEqual(len(facts), 2)
        self.assertEqual({f.verdict for f in facts}, {"PROVEN_EMPTY"})
        self.assertFalse(any(r.would_be_busy for r in executions(p)))

    def test_known_live_statement_is_still_live_after_the_preserving_foreign_call(self):
        p = parse("db = connect()\ns = prepare(db)\nforeign(db)\nclose(db)")
        self.assertEqual(analyze(p)[0].verdict, "KNOWN_LIVE")
        self.assertTrue(all(r.would_be_busy for r in executions(p)))

    def test_unsupported_syntax_and_invalid_lifetimes_fail_closed(self):
        for body in ("escape(db)", "exec(db)", "foreign(other)", "q = prepare(db)\nforeign(db, q)"):
            with self.subTest(body=body), self.assertRaises(UnsupportedSource):
                parse(f"db = connect()\n{body}\nclose(db)")
        for body in ("finalize(missing)", "q = prepare(db)\nq = prepare(db)", "if flag:\n    finalize(missing)"):
            p = parse(f"db = connect()\n{body}\nclose(db)")
            with self.subTest(body=body), self.assertRaises(UnsupportedSource):
                analyze(p)

    def test_corpus_compares_each_admission_rule_against_concrete_busy(self):
        admitted, busy = Counter(), Counter()
        programs = paths = runs = proven_programs = 0
        for source in fixture_sources():
            p = parse(source)
            facts = {f.inputs: f for f in analyze(p)}
            programs += 1
            paths += len(facts)
            proven_programs += all(f.verdict == "PROVEN_EMPTY" for f in facts.values())
            for run in executions(p):
                runs += 1
                fact = facts[run.inputs]
                with self.subTest(source=source, inputs=run.inputs, creates=run.foreign_creations):
                    self.assertGreaterEqual(run.live_count, len(fact.known_live))
                    if fact.complete:
                        self.assertEqual(run.live_count, len(fact.known_live))
                    for policy, allows in approvals(fact, run).items():
                        if allows:
                            admitted[policy] += 1
                            busy[policy] += run.would_be_busy
        self.assertEqual((programs, paths, runs, proven_programs), (1296, 2592, 4116, 256))
        self.assertEqual({policy: (admitted[policy], busy[policy]) for policy in admitted}, {
            "local_only": (2592, 1092),
            "source_proof": (768, 0),
            "unchecked_snapshot": (2820, 1320),
            "current_snapshot": (660, 0),
            "immediate_check": (1500, 0),
        })


if __name__ == "__main__":
    unittest.main()
