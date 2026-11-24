import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tlc_adapter import backend_match, completed, control, experiment, replay_control, source


class TlcAdapterTests(unittest.TestCase):
    def test_scope_and_state_count(self):
        operators, cases = experiment()
        self.assertEqual(len(cases), 798)
        self.assertEqual(sum(1 + len(row["trace"]) for row in cases), 2778)
        text = source("Cases", operators, cases)
        self.assertIn("caseId \\in 1..798", text)
        self.assertIn("registers = Replay[caseId][position + 1]", text)
        self.assertIn("mismatch = Proposed[caseId][position + 1]", text)

    def test_outcome_requires_complete_clean_graph(self):
        line = "Model checking completed. No error has been found.\n"
        good = line + "3576 states generated, 2778 distinct states found, 0 states left on queue.\n"
        for code, output, error, accepted in [
            (0, good, "", True), (1, good, "", False), (0, good, "fatal", False),
            (0, good.replace("2778", "2777"), "", False),
            (0, good.replace("0 states", "1 states"), "", False),
        ]:
            with self.subTest(code=code, output=output, error=error):
                self.assertEqual(completed(subprocess.CompletedProcess([], code, output, error),
                                           2778), accepted)

    def test_counterexample_replay_rejects_changed_registers(self):
        machine, _, record = control(final_only=False)
        states = [
            [1, {"caseId": 1, "position": 0, "registers": [0], "mismatch": False}],
            [2, {"caseId": 1, "position": 1, "registers": [-1], "mismatch": True}],
        ]
        result = subprocess.CompletedProcess([], 12, "Error: Invariant Classification is violated.", "")
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "trace.json"
            trace.write_text(json.dumps({"counterexample": {"state": states}}))
            self.assertTrue(replay_control(machine, record, result, trace))
            states[1][1]["registers"] = [-2]
            trace.write_text(json.dumps({"counterexample": {"state": states}}))
            self.assertFalse(replay_control(machine, record, result, trace))

    def test_comparison_rejects_stale_model_and_abstention(self):
        _, records = experiment()
        record = records[0]
        good = {**record, "status": "kernel-checked", "relation": "equal"}
        self.assertTrue(backend_match(json.dumps(good), [record], "lean"))
        self.assertFalse(backend_match(json.dumps({**good, "model_sha256": "stale"}), [record], "lean"))
        self.assertFalse(backend_match(json.dumps({**good, "status": "abstain"}), [record], "lean"))


if __name__ == "__main__":
    unittest.main()
