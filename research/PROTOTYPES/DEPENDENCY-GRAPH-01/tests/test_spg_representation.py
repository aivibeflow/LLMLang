"""Reproduction corpus for the RT-05 typed SPG study."""

from dataclasses import replace
from itertools import product
import json
import unittest

from src.identity_lifecycle import Binding, Lineage, Relation, Slot, State, compare
from src.persistence import dumps_graph, loads_graph
from src.recursive_identity import RecursiveIdentityError
from src.semantic_graph import RelationStore
from src.spg_representation import (
    FuelExhausted, Graph, Implementation, Operation, Prefix, Program, RepresentationError,
    compile_program, observe,
)


def dispatch_program() -> Program:
    return Program(
        contracts={
            "provider": (("first", "last"), ("last", "first")),
            "forward": (("first", "last"), ("last", "first")),
            "quiet": ((),),
        },
        operations={
            "provider": Operation("Provide", ("Int",), "Int", "provider"),
            "late": Operation("Late", ("Int",), "Int", "forward"),
            "direct": Operation("Direct", ("Int",), "Int", "forward"),
            "other": Operation("Other", ("Int",), "Int", "quiet"),
        },
        implementations={
            "primary": Implementation("provider", ("n",), 'emit("first", emit("last", n + 1))'),
            "alternate": Implementation("provider", ("n",), 'emit("first", emit("last", n + 2))'),
            "late": Implementation("late", ("n",), 'op("provider", n)'),
            "direct": Implementation("direct", ("n",), 'pin("primary", n)'),
            "other": Implementation("other", ("n",), "n - 2"),
        },
        bindings={"provider": "primary"},
    )


def prefix(term) -> Prefix:
    return Prefix(json.dumps(term))


def replace_body(program: Program, slot: str, body: str | Prefix) -> Program:
    return replace(program, implementations={
        **program.implementations, slot: replace(program.implementations[slot], body=body),
    })


def changed_selections(left: Graph, right: Graph) -> set[str]:
    old, new = left.snapshot.mapping, right.snapshot.mapping
    return {slot for slot in old.keys() | new.keys() if old.get(slot) != new.get(slot)}


def encode(graph: Graph) -> bytes:
    return dumps_graph(graph.store, RelationStore(), (graph.snapshot,))


class TypedRepresentationExperiment(unittest.TestCase):
    def test_two_expression_surfaces_match_structurally_and_against_a_trace_oracle(self):
        for offset, (operator, symbol), (yes, no), mode in product(
            (-2, 0, 1, 7), (("add", "+"), ("sub", "-")),
            (("open", "close"), ("close", "open")), ("op", "pin"),
        ):
            with self.subTest(offset=offset, operator=operator, yes=yes, mode=mode):
                operations = {
                    "compute": Operation("Compute", ("Int",), "Int", "effects"),
                    "entry": Operation("Entry", ("Int",), "Int", "effects"),
                }
                contract = (("argument", yes), ("argument", no), (yes,), (no,))
                infix = Program({"effects": contract}, operations, {
                    "compute": Implementation("compute", ("x",),
                        f' (emit("{yes}", (x {symbol} {offset:#x})) if x == 0\n'
                        f'  else emit("{no}", (x {symbol} {offset:#x}))) # fixture'),
                    "entry": Implementation("entry", ("x",),
                                            f'{mode}("compute", emit("argument", x))'),
                }, {"compute": "compute"})
                prefix_program = Program({"effects": tuple(reversed(contract))},
                                         dict(reversed(tuple(operations.items()))), {
                    "entry": Implementation("entry", ("input",),
                        prefix([mode, "compute", ["emit", "argument", ["arg", "input"]]])),
                    "compute": Implementation("compute", ("operand",),
                        prefix(["if", ["eq", ["arg", "operand"], 0],
                         ["emit", yes, [operator, ["arg", "operand"], offset]],
                         ["emit", no, [operator, ["arg", "operand"], offset]]])),
                }, {"compute": "compute"})
                first, second = compile_program(infix), compile_program(prefix_program)
                self.assertEqual(first.snapshot, second.snapshot)
                self.assertEqual(encode(first), encode(second))
                for value in range(-3, 4):
                    answer = value + (offset if operator == "add" else -offset)
                    expected = (answer, ("argument", yes if value == 0 else no))
                    for graph in (first, second):
                        actual = observe(graph, "entry", (value,))
                        self.assertIs(type(actual[0]), int)
                        self.assertEqual(actual, expected)

    def test_effect_order_is_observable_even_when_result_and_event_set_match(self):
        program = dispatch_program()
        forward = compile_program(program)
        backward = compile_program(replace_body(
            program, "primary", 'emit("last", n) + emit("first", 1)',
        ))
        # Swapping the operands is a stronger negative control: the same
        # addition, literals and labels give a different observation.
        swapped = compile_program(replace_body(
            program, "primary", 'emit("first", 1) + emit("last", n)',
        ))
        self.assertEqual(observe(forward, "late", (4,)), (5, ("first", "last")))
        self.assertEqual(observe(backward, "late", (4,)), (5, ("last", "first")))
        self.assertEqual(observe(swapped, "late", (4,)), (5, ("first", "last")))
        self.assertIn("implementation:primary", changed_selections(backward, swapped))
        self.assertIn("implementation:primary", changed_selections(forward, swapped))

    def test_ordered_arguments_and_lazy_branches_survive_lowering(self):
        program = Program({"events": (("left", "right"), ("right", "left"), ("other",), ())}, {
            "sub": Operation("Sub", ("Int", "Int"), "Int", "events"),
            "entry": Operation("Entry", ("Int", "Bool"), "Int", "events"),
        }, {
            "sub": Implementation("sub", ("x", "y"), "x - y"),
            "entry": Implementation("entry", ("x", "choose"),
                'op("sub", emit("left", x), emit("right", x + 1)) if choose else emit("other", x)'),
        }, {"sub": "sub"})
        changed = replace_body(program, "entry", prefix(["if", ["arg", "choose"],
             ["op", "sub", ["emit", "right", ["add", ["arg", "x"], 1]],
              ["emit", "left", ["arg", "x"]]], ["emit", "other", ["arg", "x"]]]))
        first, second = compile_program(program), compile_program(changed)
        self.assertEqual(observe(first, "entry", (4, False)), (4, ("other",)))
        self.assertEqual(observe(first, "entry", (4, True)), (-1, ("left", "right")))
        self.assertEqual(observe(second, "entry", (4, True)), (1, ("right", "left")))
        self.assertEqual(changed_selections(first, second), {"implementation:entry"})

    def test_binding_and_exact_call_granularity(self):
        program = dispatch_program()
        baseline = compile_program(program)
        rebound = compile_program(replace(program, bindings={"provider": "alternate"}))
        self.assertEqual(changed_selections(baseline, rebound), {"binding:provider"})
        self.assertEqual(observe(baseline, "late", (4,)), (5, ("first", "last")))
        self.assertEqual(observe(rebound, "late", (4,)), (6, ("first", "last")))
        self.assertEqual(observe(rebound, "direct", (4,)), (5, ("first", "last")))

        retargeted = compile_program(replace_body(program, "direct", 'op("provider", n)'))
        self.assertEqual(changed_selections(baseline, retargeted), {"implementation:direct"})
        self.assertEqual(observe(retargeted, "direct", (4,)), observe(baseline, "direct", (4,)))

        edited = compile_program(replace_body(program, "primary", 'emit("first", emit("last", n + 3))'))
        self.assertEqual(changed_selections(baseline, edited), {
            "binding:provider", "implementation:primary", "implementation:direct",
        })
        self.assertEqual(observe(edited, "direct", (4,)), (7, ("first", "last")))

    def test_contract_set_canonicalization_keeps_trace_order_and_multiplicity(self):
        program = dispatch_program()

        def with_traces(traces):
            return compile_program(replace(program, contracts={**program.contracts, "provider": traces}))

        reordered = with_traces((("last", "first"), ("first", "last"), ("last", "first")))
        self.assertEqual(encode(compile_program(program)), encode(reordered))
        baseline = with_traces((("first", "last"),))
        for altered in (("last", "first"), ("first", "first", "last")):
            with self.subTest(altered=altered):
                revised = with_traces((altered,))
                self.assertEqual(changed_selections(baseline, revised), {
                    "contract:provider", "operation:provider", "implementation:primary",
                    "implementation:alternate", "implementation:direct", "implementation:late",
                    "binding:provider",
                })
                # The representation records a binding declaration, even when
                # the observed trace is outside the declared contract set.
                _, trace = observe(revised, "late", (4,))
                self.assertNotEqual(trace, altered)

    def test_exported_name_changes_the_operation_where_local_parameter_name_does_not(self):
        program = dispatch_program()
        baseline = compile_program(program)
        aliased = replace(program, implementations={**program.implementations,
            "other": Implementation("other", ("argument",), "argument - 2"),
        })
        self.assertEqual(encode(baseline), encode(compile_program(aliased)))
        exported = replace(aliased, operations={**program.operations,
            "other": replace(program.operations["other"], export="OtherV2"),
        })
        self.assertEqual(changed_selections(baseline, compile_program(exported)), {
            "operation:other", "implementation:other",
        })

    def test_selected_values_round_trip_and_source_locations_are_separate(self):
        graph = compile_program(dispatch_program())
        state = encode(graph)
        store, _, (snapshot,) = loads_graph(state)
        restored = Graph(store, snapshot)
        self.assertEqual(encode(restored), state)
        self.assertEqual(observe(restored, "late", (3,)), (4, ("first", "last")))
        subject = snapshot.mapping["implementation:primary"]
        before, after = RelationStore(), RelationStore()
        before.add(snapshot.root_hash, subject, "origin", "old/source")
        after.add(snapshot.root_hash, subject, "origin", "new/source")
        after.add(snapshot.root_hash, subject, "reported_evidence", "new/run")
        self.assertNotEqual(dumps_graph(store, before, (snapshot,)), dumps_graph(store, after, (snapshot,)))
        self.assertEqual(encode(restored), state)

    def test_typed_recursive_calls_in_both_group_encodings(self):
        ops = {name: Operation(name.title(), ("Int",), "Bool", "quiet")
               for name in ("even", "odd", "entry", "other")}
        program = Program({"quiet": ((),)}, ops, {
            "odd": Implementation("odd", ("n",), 'False if n == 0 else pin("even", n - 1)', "b"),
            "even": Implementation("even", ("n",), 'True if n == 0 else pin("odd", n - 1)', "a"),
            "entry": Implementation("entry", ("n",), 'pin("even", n)'),
            "other": Implementation("other", ("n",), "True"),
        }, {})
        with self.assertRaisesRegex(RecursiveIdentityError, "dag-only"):
            compile_program(program, "dag-only")
        for mode in ("keyed", "structural"):
            with self.subTest(mode=mode):
                graph = compile_program(program, mode)
                for value in range(13):
                    answer, trace = observe(graph, "entry", (value,), fuel=value + 2)
                    self.assertIs(answer, value % 2 == 0)
                    self.assertEqual(trace, ())
                with self.assertRaises(FuelExhausted):
                    observe(graph, "entry", (2,), fuel=3)
                split = compile_program(replace_body(program, "odd", "False"), mode)
                self.assertEqual(changed_selections(graph, split), {
                    "implementation:odd", "implementation:even", "implementation:entry",
                })
                self.assertEqual(observe(split, "entry", (2,)), (False, ()))

    def test_symmetric_recursive_values_keep_separate_managed_selections(self):
        program = Program({"quiet": ((),)}, {
            "parity": Operation("Parity", ("Int",), "Bool", "quiet"),
        }, {
            "a": Implementation("parity", ("n",), 'True if n == 0 else pin("b", n - 1)', "a"),
            "b": Implementation("parity", ("n",), 'True if n == 0 else pin("a", n - 1)', "b"),
        }, {})
        structural, keyed = compile_program(program), compile_program(program, "keyed")
        a, b = "implementation:a", "implementation:b"
        self.assertEqual(structural.snapshot.mapping[a], structural.snapshot.mapping[b])
        self.assertNotEqual(keyed.snapshot.mapping[a], keyed.snapshot.mapping[b])
        for slot, value in product(("a", "b"), range(5)):
            self.assertEqual(observe(structural, slot, (value,)), (True, ()))
            self.assertEqual(observe(keyed, slot, (value,)), (True, ()))

    def test_equal_values_require_explicit_split_merge_or_replacement_evidence(self):
        program = dispatch_program()
        source = program.implementations["other"]
        plans = ({"one": source}, {"left": source, "right": source}, {"new": source})
        original, split, replacement = [compile_program(replace(
            program, implementations=rows, bindings={},
        )) for rows in plans]

        def state(graph):
            context = graph.snapshot.mapping["operation:other"]
            bindings = []
            for key, address in graph.snapshot.selections:
                if key.startswith("implementation:"):
                    slot = key.removeprefix("implementation:")
                    bindings.append(Binding(Slot("impl", slot), address, context, slot))
            return State(tuple(bindings))

        before, after, recreated = map(state, (original, split, replacement))
        self.assertEqual(len({binding.value_hash for binding in after.bindings + before.bindings}), 1)
        self.assertNotEqual(original.snapshot, split.snapshot)
        missing = compare(split.store, before, after, "lineage")
        self.assertEqual((len(missing.unmatched_before), len(missing.unmatched_after)), (1, 2))
        for kind, old, new in (("split", before, after), ("merge", after, recreated)):
            relation = Relation(kind, tuple(row.slot for row in old.bindings),
                                tuple(row.slot for row in new.bindings))
            evidence = Lineage(old.revision, new.revision, (relation,))
            self.assertEqual(compare(split.store, old, new, "lineage", lineage=evidence).relations, (relation,))
            with self.assertRaisesRegex(ValueError, "another revision pair"):
                modified = State(tuple(replace(row, alias="edited") for row in new.bindings))
                compare(split.store, old, modified, "lineage", lineage=evidence)
        self.assertEqual(compare(split.store, before, recreated, "lineage").relations, ())

    def test_invalid_or_unresolved_source_does_not_produce_a_snapshot(self):
        program = dispatch_program()
        cases = (
            (replace_body(program, "primary", "n + True"), "Int operands"),
            (replace_body(program, "primary", "n if 1 else 0"), "Bool test"),
            (replace_body(program, "primary", "n if True else False"), "matching arm types"),
            (replace_body(program, "primary", "missing"), "unknown parameter"),
            (replace_body(program, "primary", 'pin("missing", n)'), "unknown implementation"),
            (replace_body(program, "primary", 'pin("direct", True)'), "call argument types"),
            (replace_body(program, "primary", "True"), "result type"),
            (replace_body(program, "primary", "n * 2"), "unsupported expression"),
            (replace_body(program, "primary", "1.5"), "unsupported expression"),
            (replace_body(program, "primary", prefix(2**31)), "literal exceeds"),
            (replace_body(program, "primary", prefix(["add", ["arg", "n"]])), "unsupported prefix"),
            (replace_body(program, "primary", Prefix('["arg",]')), "invalid JSON prefix"),
            (replace_body(program, "primary", "n +"), "invalid infix"),
            (replace(program, bindings={}), "unknown operation binding"),
            (replace(program, bindings={"provider": "other"}), "required operation"),
            (replace(program, contracts={}), "unknown contract"),
        )
        for invalid, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic), self.assertRaisesRegex(RepresentationError, diagnostic):
                compile_program(invalid)
        graph = compile_program(program)
        with self.assertRaisesRegex(RepresentationError, "entry arguments"):
            observe(graph, "late", (True,))


if __name__ == "__main__":
    unittest.main()
