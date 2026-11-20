import unittest
from itertools import combinations, product

from rt04_atomic_execution import Load, Store, enumerate_executions


def interleaved_witnesses(initial, left, right):
    """Run every merge of two threads with reads of the latest write."""
    for left_slots in combinations(range(len(left) + len(right)), len(left)):
        left_steps, right_steps = iter(left), iter(right)
        writes = {loc: [f"init:{loc}"] for loc in sorted(initial)}
        sources = {}
        for slot in range(len(left) + len(right)):
            op = next(left_steps if slot in left_slots else right_steps)
            if isinstance(op, Store):
                writes[op.location].append(op.name)
            else:
                sources[op.name] = writes[op.location][-1]
        yield (
            tuple(tuple(order) for order in writes.values()),
            tuple((op.name, sources[op.name]) for op in left + right if isinstance(op, Load)),
        )


def observed_values(executions):
    return {tuple(value for _, value in e.observations) for e in executions}


class AtomicExecutionTests(unittest.TestCase):
    def test_store_buffering_distinguishes_global_order_from_acquire_release(self):
        threads = (
            (Store("wx", "x", 1, release=True), Load("ry", "y", acquire=True)),
            (Store("wy", "y", 1, release=True), Load("rx", "x", acquire=True)),
        )
        executions = tuple(enumerate_executions({"x": 0, "y": 0}, threads))
        self.assertEqual(observed_values(executions), {(0, 0), (0, 1), (1, 0), (1, 1)})
        self.assertEqual(
            observed_values(e for e in executions if e.admits_global_order), {(0, 1), (1, 0), (1, 1)}
        )

    def test_message_passing_derives_transitive_payload_order(self):
        threads = (
            (Store("payload", "x", 1), Store("ready", "flag", 1, release=True)),
            (Load("seen", "flag", acquire=True), Load("read", "x")),
        )
        executions = tuple(enumerate_executions({"flag": 0, "x": 0}, threads))
        self.assertEqual(observed_values(executions), {(0, 0), (0, 1), (1, 1)})
        published = [e for e in executions if dict(e.read_from)["seen"] == "ready"]
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0].synchronizes_with, {("ready", "seen")})
        self.assertIn(("payload", "read"), published[0].happens_before)

    def test_equal_flag_values_can_have_distinct_read_sources(self):
        initial = {"flag": 0, "x": 0}
        threads = (
            (Store("payload", "x", 1), Store("release", "flag", 1, release=True), Store("plain", "flag", 1)),
            (Load("seen", "flag", acquire=True), Load("read", "x")),
        )
        executions = tuple(enumerate_executions(initial, threads))
        self.assertEqual(len(executions), 5)
        self.assertEqual(
            {dict(e.read_from)["seen"] for e in executions if dict(e.observations) == {"seen": 1, "read": 0}},
            {"plain"},
        )
        self.assertEqual({e.modification_orders[0] for e in executions}, {("init:flag", "release", "plain")})
        global_executions = tuple(e for e in executions if e.admits_global_order)
        self.assertEqual(observed_values(global_executions), {(0, 0), (0, 1), (1, 1)})
        self.assertEqual(
            {(e.modification_orders, e.read_from) for e in global_executions},
            set(interleaved_witnesses(initial, *threads)),
        )

    def test_load_buffering_rejects_a_cycle_created_by_synchronization(self):
        threads = (
            (Load("ry", "y", acquire=True), Store("wx", "x", 1, release=True)),
            (Load("rx", "x", acquire=True), Store("wy", "y", 1, release=True)),
        )
        self.assertEqual(
            observed_values(enumerate_executions({"x": 0, "y": 0}, threads)), {(0, 0), (1, 0), (0, 1)}
        )
        relaxed = ((Load("ry", "y"), threads[0][1]), (Load("rx", "x"), threads[1][1]))
        self.assertIn((1, 1), observed_values(enumerate_executions({"x": 0, "y": 0}, relaxed)))

    def test_read_sources_respect_all_four_coherence_constraints(self):
        threads = (
            (Load("before", "x"), Store("first", "x", 1), Store("second", "x", 2)),
            (Load("r1", "x"), Load("r2", "x")),
        )
        executions = tuple(enumerate_executions({"x": 0}, threads))
        self.assertEqual({e.modification_orders for e in executions}, {(("init:x", "first", "second"),)})
        self.assertEqual(
            observed_values(executions), {(0, 0, 0), (0, 0, 1), (0, 0, 2), (0, 1, 1), (0, 1, 2), (0, 2, 2)}
        )
        threads = ((Store("w", "x", 7), Load("r", "x")),)
        self.assertEqual(observed_values(enumerate_executions({"x": 0}, threads)), {(7,)})

    def test_global_order_witnesses_match_independent_interleavings(self):
        initial = {"x": 0, "y": 0}
        choices = tuple(product(initial, ("load", "store"), (False, True)))
        broader_relations = broader_observations = 0
        for layout in product(choices, repeat=4):
            ops = tuple(
                Load(f"e{i}", loc, sync) if kind == "load" else Store(f"e{i}", loc, i + 1, sync)
                for i, (loc, kind, sync) in enumerate(layout)
            )
            threads = (ops[:2], ops[2:])
            executions = tuple(enumerate_executions(initial, threads))
            with self.subTest(layout=layout):
                relations = {
                    (e.modification_orders, e.read_from)
                    for e in executions
                    if e.admits_global_order
                }
                self.assertEqual(relations, set(interleaved_witnesses(initial, *threads)))
            broader_relations += len(executions) > len(relations)
            broader_observations += observed_values(executions) != observed_values(
                e for e in executions if e.admits_global_order
            )
        self.assertEqual((broader_relations, broader_observations), (242, 98))

    def test_rejects_unsupported_input(self):
        for threads in (
            ((Load("missing-init", "other"),),),
            ((Store("w", "x", 1), Load("w", "x")),),
            ((Load("init:x", "x"),),),
            (tuple(Load(f"r{i}", "x") for i in range(7)),),
        ):
            with self.subTest(threads=threads), self.assertRaises(ValueError):
                tuple(enumerate_executions({"x": 0}, threads))


if __name__ == "__main__":
    unittest.main()
