import shutil
import unittest
from src.formal_core import Binary, Const, Program, Return, Var, analyze_dependencies
from src.symbolic_relational import analyze_symbolically

@unittest.skipUnless(shutil.which("z3"), "Z3 executable not installed")
class SymbolicFiniteDifferentialTests(unittest.TestCase):
    def test_small_integer_examples_agree_with_finite_oracle(self):
        cases=[
            (Program((Return(Binary("mul",Var("x"),Const(0))),)),"FINITE_MODEL_INDEPENDENCE","SOLVER_REPORTED_UNSAT"),
            (Program((Return(Binary("add",Var("x"),Const(1))),)),"FINITE_MODEL_INFLUENCE","SOLVER_REPORTED_SAT"),
        ]
        for program, finite_expected, symbolic_expected in cases:
            finite=analyze_dependencies(program,{"x":(-2,-1,0,1,2)})
            symbolic=analyze_symbolically(program,{"x":"Int"})
            self.assertEqual(finite.factors[0].status,finite_expected)
            self.assertEqual(symbolic.factors[0].status,symbolic_expected)

if __name__=="__main__": unittest.main()
