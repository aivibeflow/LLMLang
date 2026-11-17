import unittest
import json
from src.formal_core import (Assign, Binary, Call, Const, Function, If, Program,
                             Return, State, Store, Unary, Var, Emit, Raise,
                             UnsupportedConstruct)
from src.qf_lia_profile import build_qf_lia_queries
from src.qf_lia_ir import (Declaration, RelationalQuery, Term, render_smt2, query_to_wire, canonical_query_json, QUERY_WIRE_SCHEMA)

class QFLIAProfileTests(unittest.TestCase):
    def build(self, program, inputs=None, state=None, visible=(), locals_=None):
        return build_qf_lia_queries(program, inputs or {"x": "Int"}, state, visible, locals_)

    def test_integer_identity_emits_qf_lia(self):
        result = self.build(Program((Return(Var("x")),)))
        smt = result.factors[0].smt2
        self.assertIn("(set-logic QF_LIA)", smt)
        self.assertNotIn("set-logic ALL", smt)
        self.assertIn("(assert (not (= i_0_L i_0_R)))", smt)

    def test_other_inputs_are_shared(self):
        result = self.build(Program((Return(Binary("add", Var("x"), Var("y"))),)),
                            {"x": "Int", "y": "Int"})
        smt = next(x.smt2 for x in result.factors if x.factor == "x")
        self.assertIn("(declare-const i_1 Int)", smt)
        self.assertNotIn("i_1_L", smt); self.assertNotIn("i_1_R", smt)

    def test_boolean_input_and_conditional(self):
        p = Program((If(Var("flag"), (Assign("v", Const(10)),), (Assign("v", Const(20)),)), Return(Var("v"))))
        result = self.build(p, {"flag": "Bool"}, locals_={"v": 0})
        self.assertIn("(ite i_0_L 10 20)", result.factors[0].smt2)

    def test_multiplication_by_positive_zero_negative_literals(self):
        for n in (3, 0, -2):
            p = Program((Return(Binary("mul", Var("x"), Const(n))),))
            self.assertIn("(set-logic QF_LIA)", self.build(p).factors[0].smt2)

    def test_literal_may_be_left_operand(self):
        p = Program((Return(Binary("mul", Const(-3), Var("x"))),))
        self.assertIn("(* (- 3) i_0_L)", self.build(p).factors[0].smt2)

    def test_inlines_pure_function(self):
        p = Program((Return(Call("twice", (Var("x"),))),),
                    {"twice": Function(("a",), Binary("mul", Var("a"), Const(2)))})
        self.assertIn("(* i_0_L 2)", self.build(p).factors[0].smt2)

    def test_selected_state_is_observed(self):
        p = Program((Store("balance", Binary("add", State("balance"), Var("x"))), Return(Const(0))))
        smt = self.build(p, state={"balance": 0}, visible=("balance",)).factors[0].smt2
        self.assertIn("(not (= (+ 0 i_0_L) (+ 0 i_0_R)))", smt)

    def test_no_outcome_string_observation(self):
        smt = self.build(Program((Return(Var("x")),))).factors[0].smt2
        self.assertNotIn('"return"', smt)
        self.assertNotIn("String", smt)

    def test_rejects_string_input(self):
        with self.assertRaises(UnsupportedConstruct): self.build(Program((Return(Const(0)),)), {"s": "String"})

    def test_rejects_string_literal(self):
        with self.assertRaises(UnsupportedConstruct): self.build(Program((Return(Const("x")),)))

    def test_rejects_string_initial_local(self):
        with self.assertRaises(UnsupportedConstruct): self.build(Program((Return(Const(0)),)), locals_={"s": "x"})

    def test_rejects_variable_times_variable(self):
        p = Program((Return(Binary("mul", Var("x"), Var("y"))),))
        with self.assertRaises(UnsupportedConstruct): self.build(p, {"x": "Int", "y": "Int"})

    def test_rejects_expression_times_expression_even_if_constant(self):
        p = Program((Return(Binary("mul", Var("x"), Binary("add", Const(2), Const(3)))),))
        with self.assertRaises(UnsupportedConstruct): self.build(p)

    def test_rejects_bool_as_int(self):
        p = Program((Return(Binary("add", Var("x"), Const(True))),))
        with self.assertRaises(UnsupportedConstruct): self.build(p)

    def test_rejects_unsupported_operator(self):
        p = Program((Return(Binary("div", Var("x"), Const(2))),))
        with self.assertRaises(UnsupportedConstruct): self.build(p)

    def test_rejects_recursive_function(self):
        p = Program((Return(Call("f", (Var("x"),))),),
                    {"f": Function(("a",), Call("f", (Var("a"),)))})
        with self.assertRaises(UnsupportedConstruct): self.build(p)

    def test_rejects_unreachable_function_body(self):
        p = Program((Return(Var("x")),), {"unused": Function(("a",), Var("a"))})
        with self.assertRaises(UnsupportedConstruct): self.build(p)

    def test_rejects_effects(self):
        p = Program((Emit("out", Var("x")), Return(Const(0))))
        with self.assertRaises(UnsupportedConstruct): self.build(p)

    def test_rejects_early_raise(self):
        p = Program((Raise(Const(1)), Return(Const(0))))
        with self.assertRaises(UnsupportedConstruct): self.build(p)

    def test_rejects_uninitialized_observation(self):
        with self.assertRaises(UnsupportedConstruct):
            self.build(Program((Return(Const(0)),)), state={}, visible=("missing",))

    def test_deterministic_rendering_and_digest(self):
        p = Program((Return(Binary("add", Var("x"), Const(1))),))
        a, b = self.build(p), self.build(p)
        self.assertEqual(a.factors, b.factors)
        self.assertEqual(a.ir_digest, b.ir_digest)
        self.assertEqual(len(a.factors[0].query_sha256), 64)
        self.assertEqual(len(a.factors[0].query_ir_digest), 64)
        self.assertTrue(a.validator_version)
        self.assertTrue(a.encoder_version)

    def test_supported_boolean_and_linear_operators(self):
        expr = Binary("and", Unary("not", Var("flag")),
                      Binary("le", Unary("neg", Var("x")), Const(4)))
        p = Program((Return(expr),))
        smt = self.build(p, {"flag": "Bool", "x": "Int"}).factors[0].smt2
        self.assertIn("(and (not i_0_L)", smt)
        self.assertIn("(<= (- i_1) 4)", smt)

    def test_per_factor_query_ir_digests_are_distinct(self):
        p = Program((Return(Binary("add", Var("x"), Var("y"))),))
        result = self.build(p, {"x": "Int", "y": "Int"})
        self.assertNotEqual(result.factors[0].query_ir_digest, result.factors[1].query_ir_digest)

    def test_query_ir_is_typed_and_is_renderer_source(self):
        result = self.build(Program((Return(Var("x")),)))
        query = result.factors[0].query_ir
        self.assertIsInstance(query, RelationalQuery)
        self.assertIsInstance(query.factor_difference, Term)
        self.assertEqual(render_smt2(query), result.factors[0].smt2)

    def test_renderer_rejects_nonlinear_query_ir(self):
        x, y = Term("symbol", "Int", atom="x"), Term("symbol", "Int", atom="y")
        nonlinear = Term("mul", "Int", (x, y))
        diff = Term("not", "Bool", (Term("eq", "Bool", (x, y)),))
        query = RelationalQuery("x", (Declaration("x", "Int"), Declaration("y", "Int")), diff,
                                Term("not", "Bool", (Term("eq", "Bool", (nonlinear, x)),)))
        with self.assertRaises(UnsupportedConstruct): render_smt2(query)

    def test_canonical_query_json_wire_schema_is_versioned_and_deterministic(self):
        result = self.build(Program((Return(Var("x")),)))
        query = result.factors[0].query_ir
        first = canonical_query_json(query)
        self.assertEqual(first, canonical_query_json(query))
        wire = json.loads(first)
        self.assertEqual(wire["schema"], QUERY_WIRE_SCHEMA)
        self.assertEqual(wire["schema"], "llmlang.qf_lia.relational-query/1")
        self.assertEqual(set(wire), {
            "schema", "factor", "declarations", "factor_difference",
            "observations_differ", "observation_contract"
        })
        self.assertEqual(wire, query_to_wire(query))
        self.assertEqual(set(wire["factor_difference"]), {"op", "sort", "args", "atom"})

    def test_boolean_arithmetic_is_rejected(self):
        p = Program((Return(Binary("add", Var("x"), Const(1))),))
        with self.assertRaises(UnsupportedConstruct): self.build(p, {"x": "Bool"})

if __name__ == "__main__": unittest.main()
