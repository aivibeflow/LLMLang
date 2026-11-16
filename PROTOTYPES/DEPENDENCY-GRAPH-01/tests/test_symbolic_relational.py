import sys
import tempfile
import unittest
from pathlib import Path
from src.formal_core import Assign, Binary, Call, Const, Emit, Function, If, Program, Return, Store, Var
from src.symbolic_relational import analyze_symbolically

class SymbolicRelationalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fake = Path(self.tmp.name) / "solver.py"
    def tearDown(self):
        self.tmp.cleanup()
    def solver(self, output):
        self.fake.write_text("import sys\nsys.stdin.read()\nprint(" + repr(output) + ")\n")
        return (sys.executable, str(self.fake))
    def test_sat_returns_influence_and_pair_witness(self):
        p = Program((Return(Binary("add", Var("x"), Const(1))),))
        r = analyze_symbolically(p, {"x":"Int"}, solver_command=self.solver('sat\n((in_0_L 0) (in_0_R 1))'))
        self.assertEqual(r.factors[0].status,"SOLVER_REPORTED_SAT")
        self.assertEqual(r.factors[0].witness,({"x":0},{"x":1}))
        self.assertIn("(assert (not (= in_0_L in_0_R)))",r.smt_queries[0][1])
        self.assertNotIn("(get-value",r.smt_queries[0][1])
    def test_get_value_is_requested_only_after_sat(self):
        capture = Path(self.tmp.name) / "solver-inputs.txt"
        self.fake.write_text(
            "import sys\n"
            "data=sys.stdin.read()\n"
            + "with open(" + repr(str(capture)) + ", 'a') as f: f.write(repr(data) + chr(10))\n"
            + "print('sat')\n"
            + "if '(get-value' in data: print('((in_0_L 0) (in_0_R 1))')\n"
        )
        p = Program((Return(Binary("add", Var("x"), Const(1))),))
        r = analyze_symbolically(p, {"x":"Int"}, solver_command=(sys.executable, str(self.fake)))
        self.assertEqual(r.factors[0].status, "SOLVER_REPORTED_SAT")
        calls = capture.read_text().splitlines()
        self.assertEqual(len(calls), 2)
        self.assertNotIn("(get-value", calls[0])
        self.assertIn("(get-value", calls[1])

    def test_unsat_proves_independence(self):
        p=Program((Return(Binary("mul",Var("x"),Const(0))),))
        r=analyze_symbolically(p,{"x":"Int"},solver_command=self.solver("unsat"))
        self.assertEqual(r.factors[0].status,"SOLVER_REPORTED_UNSAT")
    def test_unknown_is_not_independence(self):
        p=Program((Return(Var("x")),))
        r=analyze_symbolically(p,{"x":"Int"},solver_command=self.solver("unknown"))
        self.assertEqual(r.factors[0].status,"UNKNOWN"); self.assertEqual(r.status,"UNKNOWN")
    def test_missing_solver_is_unknown(self):
        p=Program((Return(Var("x")),))
        r=analyze_symbolically(p,{"x":"Int"},solver_command=("no-such-smt-solver",))
        self.assertEqual(r.factors[0].status,"UNKNOWN")
    def test_timeout_is_unknown(self):
        self.fake.write_text("import time\ntime.sleep(2)\n")
        p=Program((Return(Var("x")),))
        r=analyze_symbolically(p,{"x":"Int"},solver_command=(sys.executable,str(self.fake)),timeout_seconds=0.01)
        self.assertEqual(r.factors[0].status,"UNKNOWN")
    def test_other_inputs_are_shared(self):
        p=Program((Return(Binary("add",Var("x"),Var("y"))),))
        r=analyze_symbolically(p,{"x":"Int","y":"Int"},solver_command=self.solver("unsat"))
        smt=dict(r.smt_queries)["x"]
        self.assertIn("(declare-const in_0_L Int)",smt)
        self.assertIn("(declare-const in_0_R Int)",smt)
        self.assertIn("(declare-const in_1 Int)",smt)
        self.assertNotIn("in_1_L",smt); self.assertNotIn("in_1_R",smt)
    def test_rejects_unsupported_sort(self):
        with self.assertRaises(ValueError):
            analyze_symbolically(Program((Return(Var("x")),)),{"x":"Real"})
    def test_if_branch_uses_ite(self):
        p=Program((If(Var("flag"),(Assign("v",Const(10)),),(Assign("v",Const(20)),)),Return(Var("v"))))
        r=analyze_symbolically(p,{"flag":"Bool"},solver_command=self.solver("unsat"),initial_locals={"v":0})
        self.assertIn("(ite in_0_L",dict(r.smt_queries)["flag"])
    def test_state_observation_is_included(self):
        p=Program((Store("balance",Var("delta")),Return(Const(0))))
        r=analyze_symbolically(p,{"delta":"Int"},{"balance":0},["balance"],
            solver_command=self.solver('sat\n((in_0_L 1) (in_0_R 2))'))
        smt=dict(r.smt_queries)["delta"]
        self.assertIn("state:balance",r.factors[0].changed_observations)
        self.assertIn("(not (= in_0_L in_0_R))",smt)
    def test_unsupported_effect_returns_unknown(self):
        p=Program((Emit("out",Var("x")),Return(Const(0))))
        r=analyze_symbolically(p,{"x":"Int"},solver_command=self.solver("unsat"))
        self.assertEqual(r.factors[0].status,"UNKNOWN"); self.assertEqual(r.smt_queries,())
    def test_pure_function_is_inlined(self):
        p=Program((Return(Call("twice",(Var("x"),))),),
            {"twice":Function(("a",),Binary("mul",Var("a"),Const(2)))})
        r=analyze_symbolically(p,{"x":"Int"},solver_command=self.solver('sat\n((in_0_L 0) (in_0_R 1))'))
        self.assertEqual(r.factors[0].status,"SOLVER_REPORTED_SAT")
        self.assertIn("(* in_0_L 2)",dict(r.smt_queries)["x"])

if __name__=="__main__": unittest.main()
