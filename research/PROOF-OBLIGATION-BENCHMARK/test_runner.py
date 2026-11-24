import unittest
from run import aggregate, load, run, score, read, ROOT
from coverage_matrix import check_coverage
from extended_oracles import EXTENDED


class BenchmarkTests(unittest.TestCase):
    def test_corpus(self):
        records = run(load())
        self.assertGreaterEqual(len(records), 108)
        self.assertTrue(all(r["evaluated_inputs"] > 0 for r in records))
        self.assertTrue(all(r["counterexample"] is not None for r in records if r["status"] == "disproven"))
        self.assertEqual(score(records, records)["accuracy"], 1)
        self.assertEqual(score(records, [])["accuracy"], 0)
        self.assertEqual(score(records, [])["missing"], len(records))
        with self.assertRaises(ValueError):
            score(records, records + records[:1])
        with self.assertRaises(ValueError):
            score(records, [{**records[0], "case_sha256":"stale"}])
        bad = [{**r,"status":"proven"} for r in records]
        self.assertEqual(score(records,bad)["false_proven_rate"],1)

    def test_extended_witnesses(self):
        # Hand-derived distinguishing examples, separate from the enumerator's
        # first-counterexample choice; require exact witnesses and two positives.
        witnesses = {"vacuity":0,"option":0,"division":[-2,0],"compose":-2,"retry":[0,0],"rounding":-5,"probability":"uniform-space","lost_update":["R0","R1","W0","W1"],"migration":[0,False],"trace_isolation":[0,0,1],"countdown":1,"translation":3}
        for name,witness in witnesses.items():
            with self.subTest(oracle=name):
                for variant in ("reference","alternative","mutation"):
                    rows = list(EXTENDED[name](variant))
                    matches = [ok for x,ok in rows if x == witness]
                    self.assertEqual(matches,[variant != "mutation"])
        # The three interleaving positions for thread 0 select all six schedules.
        self.assertEqual(len(list(EXTENDED["lost_update"]("reference"))),6)

    def test_coverage_matrix(self):
        cases = load()
        taxonomy = read(ROOT/"taxonomy.json")
        target = read(ROOT/"coverage-target.json")
        report = check_coverage(cases,taxonomy,target)
        self.assertEqual(report["covered_cells"],80)
        self.assertEqual(report["target_cells"],80)
        missing = {**target,"mapping":{k:v for k,v in target["mapping"].items() if k!="FORM-01"}}
        with self.assertRaises(ValueError):
            check_coverage(cases,taxonomy,missing)
        wrong = {**target,"probes":{**target["probes"],"POB-025":{**target["probes"]["POB-025"],"outside":[1,0]}}}
        with self.assertRaises(ValueError):
            check_coverage(cases,taxonomy,wrong)
        for record in run(cases):
            if record["obligation_records"] is not None:
                self.assertEqual([x["id"] for x in record["obligation_records"]],["O1","O2"])
                self.assertGreater(record["outside_assumption_inputs"],0)

    def test_aggregation(self):
        good = dict(id="a",status="proven",identity_checked=True,correspondence_checked=True,evidence_checked=True,assumptions_discharged=True,dependencies_closed=True,scope_sufficient=True)
        self.assertEqual(aggregate([good],["a"]),"proven")
        self.assertEqual(aggregate([good],["a","b"]),"unknown")
        self.assertEqual(aggregate([good,good],["a"]),"unknown")
        for flag in ("identity_checked","correspondence_checked","evidence_checked","assumptions_discharged","dependencies_closed","scope_sufficient"):
            self.assertEqual(aggregate([{**good,flag:False}],["a"]),"unknown")
        for status in ("bounded_pass","unknown","unsupported","error"):
            self.assertEqual(aggregate([{**good,"status":status}],["a"]),"unknown")
        bad = {**good,"status":"disproven","counterexample_validated":True}
        self.assertEqual(aggregate([bad],["a"]),"disproven")
        self.assertEqual(aggregate([{**bad,"correspondence_checked":False}],["a"]),"unknown")


if __name__ == "__main__":
    unittest.main()
