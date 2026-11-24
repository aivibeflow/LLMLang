import io
import unittest
from explore import explore,Unsupported
from models import FAMILIES,ACTIONS,DEPTH,CONTRACTS,initial,step
from generate import check,replay,build
from oracle import check as predicate


def row(f,k):
    return {"id":"test","family":f,"parameter":k,"contract":CONTRACTS[f],"initial":initial(f,k),"actions":list(ACTIONS[f]),"depth":DEPTH[f]}


class SystemTests(unittest.TestCase):
    def test_families(self):
        for f in FAMILIES:
            for k in (1,7):
                with self.subTest(f=f,k=k):
                    r=row(f,k); results=check(r)
                    for v in ("reference","alternative"):
                        self.assertEqual(results[v]["status"],"bounded_pass")
                    self.assertEqual(results["mutation"]["status"],"disproven")
                    for name,o in results["mutation"]["obligations"].items():
                        if o["witness"]: self.assertFalse(replay(r,"mutation",o["witness"])[name])
    def test_distinguishing_properties(self):
        wanted={"heap_separation":"separation","graph_gc":"preservation","partition_retry":"at_most_once",
                "quorum":"agreement","fulfillment":"shipment","rolling_upgrade":"compatibility","ffi_buffer":"bounds_frame"}
        for f,o in wanted.items():
            with self.subTest(f=f):
                self.assertEqual(check(row(f,1))["mutation"]["obligations"][o]["status"],"disproven")
    def test_hand_witnesses(self):
        cases=[("heap_separation",["attach0"],"separation"),
               ("graph_gc",["collect"],"preservation"),
               ("partition_retry",["deliver","crash","recover","deliver"],"at_most_once"),
               ("quorum",["voteA0","voteA1","commitA","voteB0","voteB1","commitB"],"agreement"),
               ("fulfillment",["reserve","ship"],"shipment"),
               ("rolling_upgrade",["upgrade0","upgrade1","send_false","deliver"],"compatibility"),
               ("ffi_buffer",["grant","write_oob"],"bounds_frame")]
        for f,trace,obligation in cases:
            for variant in ("reference","mutation","alternative"):
                with self.subTest(f=f,variant=variant):
                    s=initial(f,1)
                    for a in trace:
                        b=dict(s); s,e=step(f,1,variant,s,a)
                    self.assertEqual(predicate(f,1,b,a,s,e)[obligation],variant!="mutation")
    def test_explorer(self):
        # State merging preserves all outgoing edges for local Markov properties.
        x=explore({"n":0},["stay","flip"],lambda s,a:({"n":1-s["n"] if a=="flip" else s["n"]},[]),lambda b,a,s,e:{"ok":True},3)
        self.assertEqual((x["states"],x["edges"]),(2,4))
        for depth in (0,9):
            with self.assertRaises(Unsupported): explore({"n":0},["x"],lambda s,a:(s,[]),lambda *args:{"ok":True},depth)
        with self.assertRaises(Unsupported): explore({"n":0},["x"],lambda s,a:({"n":True},[]),lambda *args:{"ok":True},1)
    def test_reproducibility(self):
        a,b=io.StringIO(),io.StringIO()
        x=build(14,42,blind_stream=a); y=build(14,42,blind_stream=b)
        self.assertEqual(x,y); self.assertEqual(a.getvalue(),b.getvalue())
        self.assertEqual(x["mutations_rejected"],14)
        self.assertNotIn('"results"',a.getvalue())


if __name__=="__main__": unittest.main()
