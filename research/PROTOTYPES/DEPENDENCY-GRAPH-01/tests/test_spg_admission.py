"""Compare digest integrity and independent typed admission on the same bytes."""

import unittest

from src.persistence import loads_graph
from src.semantic_graph import canonical_bytes, make_snapshot
from src.spg_admission import validate
from src.spg_representation import Graph, RepresentationError, compile_program, observe
from tests.test_spg_representation import dispatch_program, encode, replace_body


def reload(graph):
    store, _, (snapshot,) = loads_graph(encode(graph))
    return Graph(store, snapshot)


class SpgAdmissionExperiment(unittest.TestCase):
    def test_compiled_dag_admitted_and_replays(self):
        program = replace_body(dispatch_program(), "late", 'op("provider", pin("primary", n))')
        graph = reload(compile_program(program, "dag-only"))
        validate(graph)
        for entry, offset in (("late", 2), ("direct", 1)):
            for n in range(-3, 4):
                with self.subTest(entry=entry, n=n):
                    trace = ("first", "last") * offset
                    self.assertEqual(observe(graph, entry, (n,)), (n + offset, trace))

    def test_integrity_does_not_bind_an_executable_type(self):
        graph = compile_program(dispatch_program())
        selections = graph.snapshot.mapping
        body = graph.store.get(selections["implementation:other"])
        payload = body.payload
        payload[2] = {"literal": '["literal",true]'}
        selections["implementation:other"] = graph.store.put(body.kind, payload, body.dependencies)
        loaded = reload(Graph(graph.store, make_snapshot(selections)))

        actual, trace = observe(loaded, "other", (4,))
        self.assertIs(actual, True)
        self.assertEqual(trace, ())
        with self.assertRaisesRegex(RepresentationError, "body result type"):
            validate(loaded)

    def test_bad_rehashed_body_variants(self):
        for term, slot, change, diagnostic in (
            (["op", 0, ["literal", False]], "late", None, "call argument types"),
            (["op", 0, ["argument", 0]], "late", "omit-callee", "body reference/edge mismatch"),
            (["literal", 1], "late", None, "unused call references"),
            (["op", 1, ["argument", 0]], "late", None, "invalid call position"),
            (["if", ["literal", True], ["literal", 1], ["argument", True]],
             "other", None, "unsupported instruction"),
        ):
            with self.subTest(term=term, change=change):
                graph = compile_program(dispatch_program())
                selections = graph.snapshot.mapping
                key = f"implementation:{slot}"
                body = graph.store.get(selections[key])
                payload = body.payload
                payload[2] = {"literal": canonical_bytes(term).decode()}
                deps = body.dependencies
                if change == "omit-callee":
                    deps = tuple(edge for edge in deps
                                 if edge.target_hash != selections["operation:provider"])
                selections[key] = graph.store.put(body.kind, payload, deps)
                loaded = reload(Graph(graph.store, make_snapshot(selections)))
                if change == "omit-callee":
                    self.assertEqual(observe(loaded, "late", (4,)), (5, ("first", "last")))
                with self.assertRaisesRegex(RepresentationError, diagnostic):
                    validate(loaded)

    def test_snapshot_cannot_borrow_a_target_from_unselected_history(self):
        for slot, diagnostic in (
            ("implementation:primary", "binding provider mismatch"),
            ("binding:provider", "operation binding missing"),
            ("operation:provider", "body owner missing from selection"),
        ):
            with self.subTest(slot=slot):
                graph = compile_program(dispatch_program())
                selections = graph.snapshot.mapping
                del selections[slot]
                loaded = reload(Graph(graph.store, make_snapshot(selections)))
                with self.assertRaisesRegex(RepresentationError, diagnostic):
                    validate(loaded)

    def test_unsupported_exact_recursive_encoding_and_conformance_boundary(self):
        program = dispatch_program()
        graph = reload(compile_program(replace_body(program, "other", 'pin("other", n)')))
        with self.assertRaisesRegex(RepresentationError, "unsupported implementation value"):
            validate(graph)

        graph = reload(compile_program(replace_body(program, "other", 'emit("unexpected", n)')))
        validate(graph)
        self.assertEqual(observe(graph, "other", (4,)), (4, ("unexpected",)))
