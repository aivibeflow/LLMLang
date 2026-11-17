from pathlib import Path
import tempfile
import unittest

from src.logos_runner import ToolPin, run_cvc5_logos, sha256_file


def executable(path: Path, source: str) -> ToolPin:
    path.write_text("#!/usr/bin/env python3\n" + source)
    path.chmod(0o755)
    return ToolPin(str(path), sha256_file(path), "test-version", "test-commit")


class LogosRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.solver_path = self.root / "fake-cvc5"
        self.logos_path = self.root / "fake-logos"
        self.logos_calls = self.root / "logos-calls.txt"
        self.query = b"(set-logic QF_LIA)\n(declare-const x Int)\n(assert (> x 0))\n(check-sat)\n"

    def tearDown(self):
        self.temp.cleanup()

    def pins(self, solver_source, logos_source="print('correct')\n"):
        solver = executable(self.solver_path, solver_source)
        logos = executable(self.logos_path, logos_source)
        return solver, logos

    def test_correct_is_unbound_not_proven(self):
        solver, logos = self.pins("print('unsat')\nprint('(proof-body)')\n")
        result = run_cvc5_logos(self.query, solver, logos)
        self.assertEqual(result.status, "CHECKER_REPORTED_CORRECT_UNBOUND")
        self.assertNotEqual(result.status, "PROVEN_INDEPENDENCE")
        self.assertEqual(result.query_sha256, __import__('hashlib').sha256(self.query).hexdigest())
        self.assertIsNotNone(result.proof_sha256)
        self.assertEqual(result.proof_bytes, b"unsat\n(proof-body)\n")

    def test_solver_sat_does_not_call_logos(self):
        solver, logos = self.pins("print('sat')\n", "open(" + repr(str(self.logos_calls)) + ", 'w').write('called')\nprint('correct')\n")
        result = run_cvc5_logos(self.query, solver, logos)
        self.assertEqual(result.status, "SOLVER_REPORTED_SAT")
        self.assertFalse(self.logos_calls.exists())

    def test_solver_unknown_does_not_call_logos(self):
        solver, logos = self.pins("print('unknown')\n")
        result = run_cvc5_logos(self.query, solver, logos)
        self.assertEqual(result.status, "SOLVER_REPORTED_UNKNOWN")

    def test_unsat_without_proof_body_is_only_solver_report(self):
        solver, logos = self.pins("print('unsat')\n")
        result = run_cvc5_logos(self.query, solver, logos)
        self.assertEqual(result.status, "SOLVER_REPORTED_UNSAT")
        self.assertIsNone(result.checker_exit_code)

    def test_logos_incorrect_is_not_proof(self):
        solver, logos = self.pins("print('unsat')\nprint('(proof)')\n", "print('incorrect')\nraise SystemExit(1)\n")
        self.assertEqual(run_cvc5_logos(self.query, solver, logos).status, "CHECKER_REPORTED_INCORRECT")

    def test_logos_incomplete_is_not_proof(self):
        solver, logos = self.pins("print('unsat')\nprint('(proof)')\n", "print('incomplete')\nraise SystemExit(2)\n")
        self.assertEqual(run_cvc5_logos(self.query, solver, logos).status, "CHECKER_REPORTED_INCOMPLETE")

    def test_unrecognized_checker_response_is_unknown(self):
        solver, logos = self.pins("print('unsat')\nprint('(proof)')\n", "print('correct')\nraise SystemExit(1)\n")
        self.assertEqual(run_cvc5_logos(self.query, solver, logos).status, "UNKNOWN")

    def test_wrong_solver_hash_fails_closed(self):
        solver, logos = self.pins("print('unsat')\nprint('(proof)')\n")
        self.solver_path.write_text("#!/usr/bin/env python3\nprint('sat')\n")
        result = run_cvc5_logos(self.query, solver, logos)
        self.assertEqual(result.status, "UNKNOWN")
        self.assertIn("SHA-256 mismatch", result.detail)

    def test_wrong_logos_hash_fails_closed(self):
        solver, logos = self.pins("print('unsat')\nprint('(proof)')\n")
        self.logos_path.write_text("#!/usr/bin/env python3\nprint('tampered')\n")
        result = run_cvc5_logos(self.query, solver, logos)
        self.assertEqual(result.status, "UNKNOWN")
        self.assertIn("SHA-256 mismatch", result.detail)

    def test_missing_solver_fails_closed(self):
        solver, logos = self.pins("print('unsat')\nprint('(proof)')\n")
        missing = ToolPin(str(self.root / "missing"), "0" * 64, "v", "c")
        self.assertEqual(run_cvc5_logos(self.query, missing, logos).status, "UNKNOWN")

    def test_solver_nonzero_exit_fails_closed(self):
        solver, logos = self.pins("print('unsat')\nraise SystemExit(3)\n")
        self.assertEqual(run_cvc5_logos(self.query, solver, logos).status, "UNKNOWN")

    def test_solver_timeout_fails_closed(self):
        solver, logos = self.pins("import time\ntime.sleep(2)\n")
        self.assertEqual(run_cvc5_logos(self.query, solver, logos, timeout_seconds=0.05).status, "UNKNOWN")

    def test_checker_timeout_fails_closed(self):
        solver, logos = self.pins("print('unsat')\nprint('(proof)')\n", "import time\ntime.sleep(2)\n")
        self.assertEqual(run_cvc5_logos(self.query, solver, logos, timeout_seconds=0.05).status, "UNKNOWN")

    def test_invalid_timeout_rejected(self):
        solver, logos = self.pins("print('unsat')\n")
        with self.assertRaises(ValueError):
            run_cvc5_logos(self.query, solver, logos, timeout_seconds=0)

    def test_tool_pin_requires_digest(self):
        with self.assertRaises(ValueError):
            ToolPin("x", "bad", "v", "c")


if __name__ == "__main__":
    unittest.main()
