import itertools, unittest
from src.formal_core import Binary,Const,Emit,If,Program,Return,Store,Var,analyze_dependencies,execute
class FiniteRelationalConsistencyTests(unittest.TestCase):
 def test_pairwise_definition(self):
  ps=[Program((Return(Binary("mul",Var("x"),Const(0))),)),
      Program((Return(Binary("add",Var("x"),Const(2))),)),
      Program((If(Var("x"),(Emit("e",Const(1)),),()),Return(Const(0)))),
      Program((Store("s",Var("x")),Return(Const(1)))),
      Program((If(Var("y"),(Return(Var("x")),),(Return(Const(0)),)),))]
  ds={"x":(0,1),"y":(False,True)}
  for p in ps:
   r=analyze_dependencies(p,ds,{"s":0},["s"])
   self.assertEqual(r.status,"DECIDED_WITHIN_FINITE_MODEL")
   rows=[dict(zip(sorted(ds),v)) for v in itertools.product(*(ds[k] for k in sorted(ds)))]
   for f in r.factors:
    diff=False
    for a in rows:
     for b in rows:
      if a[f.factor]==b[f.factor] or any(a[k]!=b[k] for k in ds if k!=f.factor): continue
      diff |= execute(p,a,{"s":0},["s"]) != execute(p,b,{"s":0},["s"])
    self.assertEqual(f.status,"FINITE_MODEL_INFLUENCE" if diff else "FINITE_MODEL_INDEPENDENCE")
if __name__=="__main__": unittest.main()
