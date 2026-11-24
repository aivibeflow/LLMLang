import copy
import io
import unittest
from machine import execute,validate,Unsupported
from templates import FAMILIES,VARIANTS,model,scenarios
from generate import build,check,blind,shrink,CONTRACTS


def row(f,k):
    return {"id":"test","family":f,"parameter":k,"contract":CONTRACTS[f],"models":{v:model(f,k,v) for v in VARIANTS}}


class TransitionTests(unittest.TestCase):
    def test_all_families(self):
        for f in FAMILIES:
            for k in (1,10):
                with self.subTest(f=f,k=k):
                    result=check(row(f,k))
                    self.assertEqual(result["reference"]["status"],"bounded_pass")
                    self.assertEqual(result["alternative"]["status"],"bounded_pass")
                    self.assertEqual(result["mutation"]["status"],"disproven")
                    for o,x in result["mutation"]["obligations"].items():
                        if x["status"]=="disproven": self.assertIsNotNone(shrink(row(f,k),o))
    def test_hand_witnesses(self):
        # Exact independently reasoned observations, not generator-selected witnesses.
        self.assertEqual(execute(model("transfer",1,"mutation"),["fail"])[0]["state"],{"a":0,"b":0})
        self.assertEqual(execute(model("lifetime",1,"reference"),["free","allocate","read"])[-1]["events"],[["absent",0]])
        self.assertEqual(execute(model("lifetime",1,"mutation"),["free","allocate","read"])[-1]["events"],[["value",2]])
        self.assertEqual(execute(model("reservation",1,"mutation"),["acquire0","acquire1"])[-1]["state"]["used"],2)
        self.assertEqual(execute(model("cancel_cleanup",1,"mutation"),["cancel"])[0]["state"]["live"],1)
        self.assertEqual(execute(model("deadline",1,"reference"),["tick","tick"])[-1]["events"],[["timeout",3]])
        self.assertEqual(execute(model("deadline",1,"mutation"),["tick","tick"])[-1]["events"],[])
        t=["read0","read1","write0","write1"]
        self.assertEqual(execute(model("interleaving",1,"mutation"),t)[-1]["state"]["counter"],2)
        self.assertEqual(execute(model("interleaving",1,"reference"),t)[-1]["state"]["counter"],3)
        self.assertEqual(len(list(scenarios("interleaving",1))),6)
        self.assertEqual(check(row("security_trace",1))["mutation"]["obligations"]["noninterference"]["status"],"disproven")
    def test_unsupported(self):
        m=model("authorized_effect",1,"reference")
        for stmt in (["set","missing",["int",1]],["set","value",["eq",["int",1],["int",1]]],["emit","missing",["int",0]],["eval","anything"],["set","value",["int",True]]):
            bad=copy.deepcopy(m); bad["actions"]["authorized"]=[stmt]
            with self.assertRaises(Unsupported): validate(bad)
        for trace in (["missing"],["authorized"]*9):
            with self.assertRaises(Unsupported): execute(m,trace)
    def test_deterministic_blind(self):
        a,b=io.StringIO(),io.StringIO()
        x=build(30,42,blind_stream=a); y=build(30,42,blind_stream=b)
        self.assertEqual(x,y); self.assertEqual(a.getvalue(),b.getvalue())
        self.assertNotEqual(x["corpus_sha256"],build(30,43)["corpus_sha256"])
        self.assertEqual(x["mutations_rejected"],30)
        self.assertEqual(set(blind(row("retry",1))),{"id","contract","parameter","initial","actions","scenario_domain","scope"})


if __name__=="__main__": unittest.main()
