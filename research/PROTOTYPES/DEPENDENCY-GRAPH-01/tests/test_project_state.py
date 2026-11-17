import json
import unittest
from src.binding import make_binding_snapshot
from src.project_state import (ProjectStateError,dumps_project_state,loads_project_state)
from src.semantic_graph import ContentStore,Dependency,RelationStore,make_snapshot,digest

class ProjectStatePersistenceTests(unittest.TestCase):
    def fixture(self):
        store=ContentStore()
        contract=store.put("contract",{"input":"Money","output":"Money"})
        impl=store.put("implementation",{"body":"tax"},[Dependency("implements",contract)])
        caller=store.put("function",{"body":"invoice"},[Dependency("calls_contract",contract)])
        relations=RelationStore()
        relations.add("project","caller","implements","REQ-1")
        snap=make_snapshot({"contract":contract,"caller":caller})
        binding=make_binding_snapshot(store,{"tax-provider":(contract,impl)})
        return store,relations,snap,binding
    def test_round_trip_graph_and_bindings_in_one_document(self):
        s,r,snap,binding=self.fixture()
        encoded=dumps_project_state(s,r,[snap],[binding])
        s2,r2,snaps2,bindings2=loads_project_state(encoded)
        self.assertEqual(s2.hashes(),s.hashes())
        self.assertEqual(r2.for_scope("project"),r.for_scope("project"))
        self.assertEqual(snaps2,(snap,))
        self.assertEqual(bindings2,(binding,))
        self.assertEqual(dumps_project_state(s2,r2,snaps2,bindings2),encoded)
    def test_binding_and_graph_roots_survive_reload(self):
        s,r,snap,binding=self.fixture()
        s2,_,snaps,bindings=loads_project_state(dumps_project_state(s,r,[snap],[binding]))
        self.assertEqual(snaps[0].root_hash,snap.root_hash)
        self.assertEqual(bindings[0].root_hash,binding.root_hash)
        self.assertEqual(bindings[0].resolve("tax-provider",snap.mapping["contract"]),
                         binding.resolve("tax-provider",snap.mapping["contract"]))
    def test_outer_checksum_detects_tampering(self):
        s,r,snap,binding=self.fixture()
        envelope=json.loads(dumps_project_state(s,r,[snap],[binding]))
        envelope["payload"]["binding_snapshots"][0]["payload"]["bindings"][0]["key"]="evil"
        with self.assertRaisesRegex(ProjectStateError,"checksum"):
            loads_project_state(json.dumps(envelope))
    def test_missing_binding_value_rejected(self):
        s,r,snap,binding=self.fixture()
        envelope=json.loads(dumps_project_state(s,r,[snap],[binding]))
        row=envelope["payload"]["binding_snapshots"][0]["payload"]["bindings"][0]
        row["implementation_hash"]="f"*64
        bp=envelope["payload"]["binding_snapshots"][0]["payload"]
        envelope["payload"]["binding_snapshots"][0]["checksum"]=digest(bp)
        envelope["payload"]["checksum"]=digest(envelope["payload"])
        with self.assertRaises(ProjectStateError): loads_project_state(json.dumps(envelope))
    def test_schema_version_rejected(self):
        s,r,snap,binding=self.fixture()
        envelope=json.loads(dumps_project_state(s,r,[snap],[binding]))
        envelope["payload"]["schema_version"]=999
        envelope["checksum"]=digest(envelope["payload"])
        with self.assertRaisesRegex(ProjectStateError,"schema"): loads_project_state(json.dumps(envelope))
if __name__=="__main__": unittest.main()
