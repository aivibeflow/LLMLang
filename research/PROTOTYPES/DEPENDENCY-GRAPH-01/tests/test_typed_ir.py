import unittest
from src.formal_core import Assign,Binary,Call,Const,Function,If,Program,Return,State,Store,Var,UnsupportedConstruct
from src.typed_ir import validate_program
class TypedIRTests(unittest.TestCase):
 def test_accepts_well_typed_program(self):
  p=Program((If(Var("flag"),(Assign("tmp",Const(1)),),(Assign("tmp",Const(2)),)),Store("balance",Binary("add",State("balance"),Var("tmp"))),Return(Var("tmp"))))
  t=validate_program(p,{"flag":"Bool"},{"balance":0},["balance"],{"tmp":0})
  self.assertEqual(t.return_type,"Int"); self.assertEqual(len(t.ir_digest),64)
 def test_rejects_bool_as_int(self):
  with self.assertRaises(UnsupportedConstruct): validate_program(Program((Return(Binary("add",Var("x"),Const(True))),)),{"x":"Int"})
 def test_rejects_unknown_variable(self):
  with self.assertRaises(UnsupportedConstruct): validate_program(Program((Return(Var("missing")),)),{"x":"Int"})
 def test_rejects_wrong_condition_type(self):
  with self.assertRaises(UnsupportedConstruct): validate_program(Program((If(Const(1),(),()),Return(Const(0))),),{"x":"Int"})
 def test_rejects_uninitialized_state_observation(self):
  with self.assertRaises(UnsupportedConstruct): validate_program(Program((Return(Const(0)),)),{"x":"Int"},observable_state=["missing"])
 def test_rejects_assignment_to_undeclared_local(self):
  with self.assertRaises(UnsupportedConstruct): validate_program(Program((Assign("z",Const(1)),Return(Const(0))),),{"x":"Int"})
 def test_rejects_recursive_function(self):
  p=Program((Return(Call("f",(Var("x"),))),),{"f":Function(("a",),Call("f",(Var("a"),)))})
  with self.assertRaises(UnsupportedConstruct): validate_program(p,{"x":"Int"})
 def test_rejects_state_access_from_pure_function(self):
  p=Program((Return(Call("f",(Var("x"),))),),{"f":Function(("a",),State("secret"))})
  with self.assertRaises(UnsupportedConstruct): validate_program(p,{"x":"Int"},{"secret":1})
 def test_hash_changes_with_observation_boundary(self):
  p=Program((Return(Const(0)),)); a=validate_program(p,{"x":"Int"},{"s":0},[]); b=validate_program(p,{"x":"Int"},{"s":0},["s"])
  self.assertNotEqual(a.ir_digest,b.ir_digest)
 def test_rejects_branch_type_join_mismatch(self):
  p=Program((If(Var("flag"),(Assign("v",Const(1)),),(Assign("v",Const(True)),)),Return(Var("v"))))
  with self.assertRaises(UnsupportedConstruct): validate_program(p,{"flag":"Bool"},initial_locals={"v":0})
if __name__=="__main__": unittest.main()
