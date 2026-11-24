import unittest
from coverage_v2 import report
from run import load,read,ROOT


class CoverageTests(unittest.TestCase):
    def test_inventory(self):
        registry=read(ROOT/"coverage-v2.json")
        result=report(load(),registry,read(ROOT/"taxonomy.json"),read(ROOT/"coverage-target.json"))
        matrix=result["pair_matrix"]
        self.assertEqual(matrix["total"],300)
        self.assertEqual(matrix["candidate_cells"]+matrix["missing_or_unadjudicated_cells"],300)
        self.assertEqual(matrix["independently_adjudicated_cells"],0)
        self.assertTrue(all(x["applicability"]=="unadjudicated" for x in matrix["cells"]))
        self.assertEqual(result["axes"]["features"]["entries"]["spatial"]["status"],"missing")
        registry["axes"]["features"]["spatial"]["manual_candidates"]=["POB-999"]
        with self.assertRaises(ValueError):
            report(load(),registry,read(ROOT/"taxonomy.json"),read(ROOT/"coverage-target.json"))


if __name__=="__main__":
    unittest.main()
