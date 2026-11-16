import unittest
from src.formal_core import (Assign,Binary,Call,Const,Emit,Function,If,Program,Raise,Return,State,Store,Unary,Var,analyze_dependencies)
class FormalCoreTests(unittest.TestCase):
 def test_cancel(self):
  r=analyze_dependencies(Program((Return(Binary("mul",Var("x"),Const(0))),)),{"x":(-2,0,3)})
  self.assertEqual(r.factors[0].status,"PROVEN_INDEPENDENCE")
 def test_data(self):
  r=analyze_dependencies(Program((Return(Binary("add",Var("x"),Const(1))),)),{"x":(0,1)})
  self.assertEqual(r.factors[0].status,"PROVEN_INFLUENCE"); self.assertIn(("x","return"),r.may_depend_edges)
 def test_control_effect(self):
  p=Program((If(Var("f"),(Emit("e",Const(1)),),(Emit("e",Const(0)),)),Return(Const("ok"))))
  self.assertIn(("f","events"),analyze_dependencies(p,{"f":(False,True)}).may_depend_edges)
 def test_unobservable_local(self):
  p=Program((If(Var("f"),(Assign("t",Const(1)),),(Assign("t",Const(2)),)),Return(Const(0))))
  self.assertEqual(analyze_dependencies(p,{"f":(False,True)}).factors[0].status,"PROVEN_INDEPENDENCE")
 def test_state_write(self):
  p=Program((Store("s",Var("x")),Return(Const(0))))
  self.assertIn(("x","state:s"),analyze_dependencies(p,{"x":(1,2)},{"s":0},["s"]).may_depend_edges)
 def test_state_read(self):
  p=Program((Store("s",Var("x")),Return(State("s"))))
  self.assertEqual(analyze_dependencies(p,{"x":(1,2)},{"s":0},["s"]).factors[0].status,"PROVEN_INFLUENCE")
 def test_pure_call(self):
  p=Program((Return(Call("f",(Var("x"),))),),{"f":Function(("a",),Binary("add",Var("a"),Const(1)))})
  self.assertEqual(analyze_dependencies(p,{"x":(1,2)}).factors[0].status,"PROVEN_INFLUENCE")
 def test_explicit_state_parameter(self):
  p=Program((Return(Call("f",(Var("x"),State("rate")))),),{"f":Function(("a","r"),Binary("mul",Var("a"),Var("r")))})
  self.assertEqual(analyze_dependencies(p,{"x":(1,2)},{"rate":20},["rate"]).factors[0].status,"PROVEN_INFLUENCE")
 def test_ignored_parameter(self):
  p=Program((Return(Call("f",(Var("x"),))),),{"f":Function(("a",),Const(0))})
  self.assertEqual(analyze_dependencies(p,{"x":(1,2)}).factors[0].status,"PROVEN_INDEPENDENCE")
 def test_error(self):
  p=Program((If(Var("bad"),(Raise(Const("e")),),(Return(Const("ok")),)),))
  self.assertEqual(analyze_dependencies(p,{"bad":(False,True)}).factors[0].status,"PROVEN_INFLUENCE")
 def test_unknown_operator(self):
  r=analyze_dependencies(Program((Return(Unary("sqrt",Var("x"))),)),{"x":(0,1),"y":(0,1)})
  self.assertEqual(r.status,"UNKNOWN"); self.assertEqual(len(r.fallback_edges),8)
 def test_budget(self):
  self.assertEqual(analyze_dependencies(Program((Return(Var("x")),)),{"x":range(5)},max_input_cases=4).status,"UNKNOWN")
 def test_factor_interaction(self):
  p=Program((Return(Binary("and",Var("x"),Var("y"))),))
  r=analyze_dependencies(p,{"x":(False,True),"y":(False,True)})
  self.assertTrue(all(f.status=="PROVEN_INFLUENCE" for f in r.factors))
 def test_typed_equality(self):
  p=Program((If(Var("f"),(Return(Const(1)),),(Return(Const(True)),)),))
  self.assertEqual(analyze_dependencies(p,{"f":(False,True)}).factors[0].status,"PROVEN_INFLUENCE")
 def test_nan_rejected(self):
  with self.assertRaises(ValueError): analyze_dependencies(Program((Return(Var("x")),)),{"x":(float("nan"),)})
if __name__=="__main__": unittest.main()
