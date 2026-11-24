import io
import unittest
from models import FAMILIES,VARIANTS
from generate import CONTRACTS,check,obligations,build


class RecursiveTests(unittest.TestCase):
    def test_all_families(self):
        for f in FAMILIES:
            with self.subTest(f=f):
                r=check({"id":"test","family":f,"parameter":2,"contract":CONTRACTS[f]})
                for v in ("reference","alternative"): self.assertEqual(r[v]["status"],"bounded_pass")
                self.assertEqual(r["mutation"]["status"],"disproven")
    def test_hand_witnesses(self):
        fixtures=[
            ("list_induction",(2,2),"step"),
            ("tree_induction",(None,(None,None)),"step"),
            ("map_fusion",((0,),(1,0,2),(0,2,1)),"pointwise"),
            ("function_extensionality",((0,0,0),(0,1,0)),"sound"),
            ("mutual_recursion",0,"base"),
            ("least_fixed_point",(((0,1),(1,2)),0),"closed"),
            ("greatest_fixed_point",((1,1,2),(0,2,0)),"post_fixed"),
            ("stream_bisimulation",((0,2),(0,0)),"sound"),
            ("lasso_until",((),((True,False),)),"sound")]
        for f,x,o in fixtures:
            for v in VARIANTS:
                with self.subTest(f=f,v=v): self.assertEqual(obligations(f,2,x,v)[o],v!="mutation")
    def test_regular_streams(self):
        for v in ("reference","alternative"):
            self.assertTrue(all(obligations("stream_bisimulation",2,((0,2),(0,2,0,2)),v).values()))
            self.assertTrue(all(obligations("lasso_until",2,(((True,False),),((False,True),)),v).values()))
    def test_reproduce(self):
        a,b=io.StringIO(),io.StringIO()
        x=build(9,42,blind_stream=a); y=build(9,42,blind_stream=b)
        self.assertEqual(x,y); self.assertEqual(a.getvalue(),b.getvalue())
        self.assertNotIn('"results"',a.getvalue())
        self.assertEqual(x["mutations_rejected"],9)
    def test_invalid_profile(self):
        for f,k in (("magic",1),("list_induction",0),("list_induction",True)):
            with self.assertRaises(ValueError): check({"id":"test","family":f,"parameter":k,"contract":CONTRACTS.get(f,"")})


if __name__=="__main__": unittest.main()
