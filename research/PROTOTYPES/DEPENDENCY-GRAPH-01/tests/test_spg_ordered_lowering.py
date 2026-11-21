"""Differential evidence for ordered lowering from the existing typed SPG."""

from dataclasses import replace
from itertools import product
import unittest

from src.spg_ordered_lowering import execute, lower
from src.spg_representation import FuelExhausted, RepresentationError, compile_program, observe
from tests.test_spg_representation import dispatch_program, replace_body


class OrderedLoweringExperiment(unittest.TestCase):
    def test_conditional_and_nested_call_agree_with_direct_observation(self):
        count = 0
        for operator, mode, offset in product(("+", "-"), ("op", "pin"), range(-2, 3)):
            target = "provider" if mode == "op" else "primary"
            program = replace_body(dispatch_program(), "late",
                f'({mode}("{target}", emit("argument", n)) {operator} {offset}'
                f' if emit("test", n == 0) else emit("fallback", n {operator} {offset}))')
            graph = compile_program(program)
            artifact = lower(graph, "late")
            for value in range(-3, 4):
                with self.subTest(operator=operator, mode=mode, offset=offset, value=value):
                    difference = offset if operator == "+" else -offset
                    expected = (difference + (1 if value == 0 else value),
                                ("test", "argument", "first", "last") if value == 0
                                else ("test", "fallback"))
                    self.assertEqual(execute(artifact, (value,)), expected)
                    self.assertEqual(observe(graph, "late", (value,)), expected)
                    count += 1
        self.assertEqual(count, 140)

    def test_declared_binding_is_an_input_to_artifact_identity(self):
        program = dispatch_program()
        old = compile_program(program)
        new = compile_program(replace(program, bindings={"provider": "alternate"}))
        self.assertEqual(old.snapshot.mapping["implementation:late"],
                         new.snapshot.mapping["implementation:late"])
        self.assertNotEqual(lower(old, "late").identity, lower(new, "late").identity)
        self.assertEqual(execute(lower(old, "late"), (4,))[0], 5)
        self.assertEqual(execute(lower(new, "late"), (4,))[0], 6)
        self.assertEqual(lower(old, "direct").identity, lower(new, "direct").identity)
        self.assertEqual(lower(old, "other").identity, lower(new, "other").identity)

    def test_reachability_and_deterministic_artifact(self):
        program = dispatch_program()
        old = compile_program(program)
        edited = compile_program(replace_body(program, "other", 'emit("edited", n)'))
        a = lower(old, "late")
        self.assertEqual(a, lower(edited, "late"))
        self.assertEqual(a, lower(old, "late"))
        self.assertEqual(len(a.functions), 2)

    def test_binding_recursion_respects_fuel_and_exact_recursion_is_unsupported(self):
        program = dispatch_program()
        dynamic = compile_program(replace_body(
            program, "primary", '0 if n == 0 else op("provider", emit("step", n - 1))',
        ))
        artifact = lower(dynamic, "late")
        self.assertEqual(execute(artifact, (3,), fuel=5), (0, ("step",) * 3))
        self.assertEqual(observe(dynamic, "late", (3,), fuel=5), (0, ("step",) * 3))
        for execute_call in (lambda: execute(artifact, (3,), fuel=4),
                             lambda: observe(dynamic, "late", (3,), fuel=4)):
            with self.assertRaises(FuelExhausted):
                execute_call()

        exact = compile_program(replace_body(program, "other", 'pin("other", n)'))
        with self.assertRaisesRegex(RepresentationError, "exact recursive"):
            lower(exact, "other")

    def test_trace_oracle_detects_a_value_preserving_reordering(self):
        graph = compile_program(replace_body(
            dispatch_program(), "other", 'emit("left", n) + emit("right", 1)',
        ))
        artifact = lower(graph, "other")
        (address, fn), = artifact.functions
        code = tuple(("emit", "right" if insn[1] == "left" else "left")
                     if insn[0] == "emit" else insn for insn in fn.code)
        mutant = replace(artifact, functions=((address, replace(fn, code=code)),))
        self.assertEqual(execute(mutant, (4,)), (5, ("right", "left")))
        self.assertEqual(observe(graph, "other", (4,)), (5, ("left", "right")))
        self.assertNotEqual(mutant.identity, artifact.identity)
