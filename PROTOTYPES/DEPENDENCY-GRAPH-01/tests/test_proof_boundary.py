import unittest,hashlib
from src.formal_core import Const,Program,Return,Binary,State,Var,UnsupportedConstruct
from src.typed_ir import validate_program,analyze_typed_symbolically
from src.proof_boundary import SolverIdentity,ProofCheckReceipt,create_evidence_record,validate_counterexample
class ProofBoundaryTests(unittest.TestCase):
 def setUp(self):
  self.typed=validate_program(Program((Return(Const(0)),)),{"x":"Int"})
  self.solver=SolverIdentity("z3","4.x","a"*64,("z3","-in","-smt2"),(("timeout","5000"),))
  self.query="(set-logic ALL)\n(check-sat)"
  self.hashes=("c"*64,"d"*64)
 def record(self,result,receipt=None):
  return create_evidence_record(self.typed,self.query,self.solver,result,*self.hashes,receipt)
 def test_unsat_without_certificate_is_not_proof(self):
  self.assertEqual(self.record("unsat").status,"SOLVER_REPORTED_UNSAT_UNCHECKED")
 def test_receipt_never_promotes_solver_result_to_checked_proof(self):
  q=hashlib.sha256(self.query.encode()).hexdigest(); receipt=ProofCheckReceipt(q,"b"*64,"checker","1.0",True)
  self.assertEqual(self.record("unsat",receipt).status,"UNAUTHENTICATED_CHECKER_RECEIPT_PRESENT")
 def test_receipt_for_other_query_rejected(self):
  with self.assertRaises(ValueError): self.record("unsat",ProofCheckReceipt("c"*64,"b"*64,"checker","1.0",True))
 def test_invalid_receipt_rejected(self):
  q=hashlib.sha256(self.query.encode()).hexdigest()
  with self.assertRaises(ValueError): self.record("unsat",ProofCheckReceipt(q,"b"*64,"checker","1.0",False))
 def test_sat_is_not_automatically_confirmed_witness(self):
  self.assertEqual(self.record("sat").status,"SOLVER_REPORTED_SAT_COUNTEREXAMPLE_UNCHECKED")
 def test_unknown_remains_unknown(self):
  self.assertEqual(self.record("unknown").status,"UNKNOWN")
 def test_solver_executable_digest_required(self):
  with self.assertRaises(ValueError): SolverIdentity("z3","4","bad",("z3",))
 def test_counterexample_replay_confirms_difference(self):
  p=Program((Return(Binary("add",Var("x"),Const(1))),)); t=validate_program(p,{"x":"Int"})
  self.assertEqual(validate_counterexample(t,"x",{"x":1},{"x":2},{},{"x":"Int"}),"COUNTEREXAMPLE_CONFIRMED_BY_REFERENCE_EVALUATOR")
 def test_counterexample_replay_rejects_invalid_pair(self):
  p=Program((Return(Binary("add",Var("x"),Const(1))),)); t=validate_program(p,{"x":"Int","y":"Int"})
  self.assertEqual(validate_counterexample(t,"x",{"x":1,"y":1},{"x":2,"y":2},{},{"x":"Int","y":"Int"}),"COUNTEREXAMPLE_REJECTED")
 def test_bad_program_rejected_before_solver(self):
  p=Program((Return(Binary("add",Var("x"),Const(True))),))
  with self.assertRaises(UnsupportedConstruct): analyze_typed_symbolically(p,{"x":"Int"},solver_command=("must-not-run",))
 def test_counterexample_replay_includes_initial_locals(self):
  p=Program((Return(Binary("add",Var("x"),Var("base"))),)); t=validate_program(p,{"x":"Int"},initial_locals={"base":10})
  self.assertEqual(validate_counterexample(t,"x",{"x":1},{"x":2},{},{"x":"Int"},{"base":10}),"COUNTEREXAMPLE_CONFIRMED_BY_REFERENCE_EVALUATOR")
 def test_toolchain_hashes_required(self):
  with self.assertRaises(ValueError): create_evidence_record(self.typed,self.query,self.solver,"unsat","bad","d"*64)
 def test_counterexample_rejects_different_initial_state_values(self):
  p=Program((Return(Binary("add",Var("x"),State("offset"))),))
  t=validate_program(p,{"x":"Int"},{"offset":7},["offset"])
  self.assertEqual(validate_counterexample(t,"x",{"x":1},{"x":2},{"offset":99},{"x":"Int"}),"COUNTEREXAMPLE_REJECTED")
 def test_counterexample_rejects_different_initial_local_values(self):
  p=Program((Return(Binary("add",Var("x"),Var("base"))),))
  t=validate_program(p,{"x":"Int"},initial_locals={"base":10})
  self.assertEqual(validate_counterexample(t,"x",{"x":1},{"x":2},{},{"x":"Int"},{"base":99}),"COUNTEREXAMPLE_REJECTED")
if __name__=="__main__": unittest.main()
