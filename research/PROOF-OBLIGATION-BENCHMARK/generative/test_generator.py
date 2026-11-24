import io
import unittest
from grammar import evaluate,Unsupported
from generate import build,instance,check,minimize,parameters
from templates import FAMILIES,make
from oracle import direct


class GeneratorTests(unittest.TestCase):
    def test_reproducible(self):
        a,b=io.StringIO(),io.StringIO()
        self.assertEqual(build(100,42,a),build(100,42,b))
        self.assertEqual(a.getvalue(),b.getvalue())
        self.assertNotEqual(build(100,42)["corpus_sha256"],build(100,43)["corpus_sha256"])
    def test_family_boundaries(self):
        for family in FAMILIES:
            for k in (-10,0,10):
                for w in (1,5):
                    for v in ("reference","mutation","alternative"):
                        self.assertEqual(evaluate(make(family,k,w,v)),direct(family,k,w,v))
                        self.assertEqual(evaluate(make(family,k,w,v)),v!="mutation")
    def test_unsupported(self):
        for e in (["var","x"],["int",True],["forall","x",1,0,["eq",["int",1],["int",1]]],["eq",["var","x"],["int",0]],["magic"],["eq",["le",["int",0],["int",1]],["int",1]],["exists","x",0,100,["eq",["var","x"],["int",0]]]):
            with self.subTest(e=e),self.assertRaises(Unsupported):
                evaluate(e)
    def test_mutation_and_shrink(self):
        for i in range(30):
            r=instance(i,42)
            result=check(r)
            self.assertEqual(result["mutation"]["status"],"disproven")
            self.assertIsNotNone(result["mutation"]["evidence"])
            s=minimize(r)
            self.assertEqual((s["origin"],s["width"]),(0,1))
            self.assertEqual(check(s)["mutation"]["status"],"disproven")
    def test_shift_invariance(self):
        for f in FAMILIES:
            for v in ("reference","mutation","alternative"):
                self.assertEqual(evaluate(make(f,-2,3,v)),evaluate(make(f,7,3,v)))


if __name__=="__main__":
    unittest.main()
