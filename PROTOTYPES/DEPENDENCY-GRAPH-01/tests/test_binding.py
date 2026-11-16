import json
import unittest
from src.binding import (BindingError,binding_verification_key,
    dumps_binding_snapshot,loads_binding_snapshot,make_binding_snapshot)
from src.semantic_graph import ContentStore,Dependency,digest

class BindingSnapshotTests(unittest.TestCase):
    def fixture(self):
        s=ContentStore()
        c=s.put("contract",{"inputs":["Money"],"output":"Money","effects":[]})
        i1=s.put("implementation",{"body":"tax_v1"},[Dependency("implements",c,"contract")])
        i2=s.put("implementation",{"body":"tax_v2"},[Dependency("implements",c,"contract")])
        caller=s.put("function",{"body":"invoice_total"},[Dependency("calls_contract",c,"tax")])
        return s,c,i1,i2,caller
    def test_swap_changes_binding_not_caller(self):
        s,c,i1,i2,caller=self.fixture()
        a=make_binding_snapshot(s,{"tax":(c,i1)})
        b=make_binding_snapshot(s,{"tax":(c,i2)})
        self.assertNotEqual(a.root_hash,b.root_hash)
        self.assertEqual(s.get(caller).dependencies[0].target_hash,c)
        self.assertEqual(a.resolve("tax",c),i1); self.assertEqual(b.resolve("tax",c),i2)
    def test_contract_mismatch_rejected(self):
        s,c,i1,_,_=self.fixture()
        other=s.put("contract",{"output":"Text"})
        snap=make_binding_snapshot(s,{"tax":(c,i1)})
        with self.assertRaisesRegex(BindingError,"does not match"): snap.resolve("tax",other)
    def test_implementation_must_declare_exact_contract(self):
        s,c,_,_,_=self.fixture(); bad=s.put("implementation",{"body":"bad"})
        with self.assertRaisesRegex(BindingError,"does not declare"):
            make_binding_snapshot(s,{"tax":(c,bad)})
    def test_wrong_kinds_rejected(self):
        s,_,i1,_,_=self.fixture(); x=s.put("constant",{"v":1})
        with self.assertRaises(BindingError): make_binding_snapshot(s,{"x":(x,i1)})
    def test_round_trip_deterministic(self):
        s,c,i1,_,_=self.fixture(); a=make_binding_snapshot(s,{"tax":(c,i1)})
        raw=dumps_binding_snapshot(a); b=loads_binding_snapshot(raw,s)
        self.assertEqual(a,b); self.assertEqual(raw,dumps_binding_snapshot(b))
    def test_tampering_rejected(self):
        s,c,i1,_,_=self.fixture(); a=make_binding_snapshot(s,{"tax":(c,i1)})
        env=json.loads(dumps_binding_snapshot(a))
        env["payload"]["bindings"][0]["implementation_hash"]="f"*64
        with self.assertRaisesRegex(BindingError,"checksum"): loads_binding_snapshot(json.dumps(env),s)
    def test_execution_verification_key_tracks_binding(self):
        s,c,i1,i2,_=self.fixture()
        a=make_binding_snapshot(s,{"tax":(c,i1)}); b=make_binding_snapshot(s,{"tax":(c,i2)})
        base=digest({"proof":"caller-contract-proof"})
        self.assertNotEqual(binding_verification_key(base,a.root_hash),
                            binding_verification_key(base,b.root_hash))
if __name__=="__main__": unittest.main()
