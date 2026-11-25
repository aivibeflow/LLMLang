import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import rt03_bounded_solver_worker as worker
from rt03_bounded_solver_worker import run_pigeonhole_query
from rt03_feasibility_outcomes import (
    SolverAnswer,
    Verdict,
    classify_solver_answer,
    retain_as_possible,
)


class BoundedSolverWorkerTests(unittest.TestCase):
    def _fake_worker(self, directory, mode):
        path = Path(directory) / "fake_worker"
        path.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys, time\n"
            f"mode = {mode!r}\n"
            "if mode == 'startup_timeout':\n"
            "    time.sleep(30)\n"
            "    raise SystemExit(0)\n"
            "if mode == 'bad_ready':\n"
            "    print('{\"kind\":\"ready\",\"protocol\":99}', flush=True)\n"
            "    time.sleep(30)\n"
            "    raise SystemExit(0)\n"
            "print(json.dumps({'kind': 'ready', 'protocol': 1}), flush=True)\n"
            "request = json.loads(sys.stdin.readline())\n"
            "if mode == 'crash':\n"
            "    os._exit(17)\n"
            "if mode == 'malformed':\n"
            "    print('not-json', flush=True)\n"
            "    time.sleep(30)\n"
            "elif mode == 'wrong_id':\n"
            "    print(json.dumps({'request_id': 'stale', 'status': 'unsat'}), flush=True)\n"
            "    time.sleep(30)\n"
            "elif mode == 'error':\n"
            "    print(json.dumps({'request_id': request['request_id'], 'status': 'error', 'reason': 'synthetic_solver_error'}), flush=True)\n"
            "    time.sleep(30)\n"
            "elif mode == 'late':\n"
            "    time.sleep(30)\n"
            "elif mode == 'unsat':\n"
            "    print(json.dumps({'request_id': request['request_id'], 'status': 'unsat'}), flush=True)\n"
            "    time.sleep(30)\n"
            "elif mode == 'sat_incomplete':\n"
            "    print(json.dumps({'request_id': request['request_id'], 'status': 'sat', 'model': {}}), flush=True)\n"
            "    time.sleep(30)\n",
            encoding="utf-8",
        )
        path.chmod(0o755)
        return path

    def test_sat_query_returns_replayable_pigeonhole_assignment(self):
        result = run_pigeonhole_query(2, 2, timeout_seconds=2)
        self.assertEqual(result.status, "sat")
        self.assertIsNone(result.reason)
        self.assertEqual(set(result.model), {
            "p0_h0", "p0_h1", "p1_h0", "p1_h1",
        })
        self.assertEqual(sum(result.model.values()), 2)
        self.assertTrue(result.worker_reaped)

    def test_small_unsat_query_completes_but_untrusted_unsat_is_not_pruning_evidence(self):
        result = run_pigeonhole_query(3, 2, timeout_seconds=2)
        self.assertEqual(result.status, "unsat")
        self.assertIsNone(result.reason)
        self.assertTrue(result.worker_reaped)
        verdict = classify_solver_answer(
            SolverAnswer(result.status, reason=result.reason), (), frozenset()
        )
        self.assertIs(verdict, Verdict.UNKNOWN)
        self.assertTrue(retain_as_possible(verdict))

    def test_hard_unsat_query_hits_real_worker_deadline_and_is_reaped(self):
        result = run_pigeonhole_query(12, 11, timeout_seconds=0.5)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason, "timeout")
        self.assertGreaterEqual(result.query_seconds, 0.5)
        self.assertTrue(result.worker_reaped)
        self.assertIsNone(result.model)
        verdict = classify_solver_answer(
            SolverAnswer(result.status, reason=result.reason), (), frozenset()
        )
        self.assertIs(verdict, Verdict.UNKNOWN)
        self.assertTrue(retain_as_possible(verdict))

    def test_nonpositive_timeout_is_rejected_before_spawning(self):
        with self.assertRaises(ValueError):
            run_pigeonhole_query(2, 2, timeout_seconds=0)

    def test_protocol_failures_and_untrusted_responses_fail_closed(self):
        cases = (
            ("startup_timeout", "unknown", "worker_startup_timeout"),
            ("bad_ready", "unknown", "worker_protocol_error"),
            ("crash", "unknown", "worker_crashed"),
            ("malformed", "unknown", "malformed_response"),
            ("wrong_id", "unknown", "request_id_mismatch"),
            ("error", "unknown", "synthetic_solver_error"),
            ("late", "unknown", "timeout"),
            ("unsat", "unsat", None),
            ("sat_incomplete", "sat", None),
        )
        for mode, expected_status, expected_reason in cases:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                executable = self._fake_worker(directory, mode)
                with patch.object(worker.sys, "executable", str(executable)):
                    result = run_pigeonhole_query(
                        2,
                        2,
                        timeout_seconds=0.08,
                        startup_timeout_seconds=0.08,
                    )

                self.assertEqual(result.status, expected_status)
                self.assertEqual(result.reason, expected_reason)
                self.assertTrue(result.worker_reaped)
                if expected_status == "unknown":
                    self.assertIsNone(result.model)
                if mode in {"unsat", "sat_incomplete"}:
                    answer = SolverAnswer(
                        result.status, model=result.model, reason=result.reason
                    )
                    variables = frozenset({"x"})
                    verdict = classify_solver_answer(answer, (), variables)
                    self.assertIs(verdict, Verdict.UNKNOWN)
                    self.assertTrue(retain_as_possible(verdict))


if __name__ == "__main__":
    unittest.main()
