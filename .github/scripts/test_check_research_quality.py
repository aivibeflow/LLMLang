"""Unit tests for the non-blocking quality-format pilot."""
import tempfile
import unittest
from pathlib import Path

from check_research_quality import inspect, is_new_report, run


COMPLETE = """# Sample

**Status:** Research only
**Baseline:** abc123
**Evidence type:** Executable
**Fixture:** fixture.json
**Tool versions:** Python 3.12.2
**Expected output:** PASS; reject count 1

## Problem and hypotheses
## Prior art and alternatives
## Formal model and assumptions
## Experiments and method
```sh
python3 -B experiment.py
```
## Results
Observation: one accepted case.
## Limitations and rejected alternatives
Negative case: failure; rejected implementation.
## Decision boundary and recommendation
## Draft impact and traceability
"""


class CheckerTests(unittest.TestCase):
    def test_complete_executable_report(self):
        self.assertEqual(inspect(COMPLETE), [])

    def test_missing_executable_reproduction_is_warned(self):
        damaged = COMPLETE.replace("**Fixture:** fixture.json\n", "").replace(
            "**Expected output:** PASS; reject count 1\n", "").replace("```sh\npython3 -B experiment.py\n```\n", "")
        findings = inspect(damaged)
        self.assertIn("executable evidence missing: Fixture", findings)
        self.assertIn("executable evidence missing: Expected output", findings)
        self.assertIn("executable evidence missing: fenced reproduction command", findings)

    def test_prior_art_does_not_require_executable_metadata(self):
        report = COMPLETE.replace("**Evidence type:** Executable", "**Evidence type:** Prior art")
        report = report.replace("**Fixture:** fixture.json\n", "").replace("**Tool versions:** Python 3.12.2\n", "").replace("**Expected output:** PASS; reject count 1\n", "")
        self.assertFalse(any("executable evidence" in f for f in inspect(report)))

    def test_existing_metadata_punctuation_is_not_a_missing_field(self):
        variants = [
            COMPLETE.replace("**Status:** Research only", "- **Status** · Research only")
                    .replace("**Baseline:** abc123", "- **Baseline** · `abc123`"),
            COMPLETE.replace("**Status:** Research only", "**Status** — Research only")
                    .replace("**Baseline:** abc123", "**Baseline** — abc123"),
        ]
        for report in variants:
            self.assertEqual(inspect(report), [])

    def test_omissions_are_warnings(self):
        findings = inspect("# Proposal\n## Conclusions\n")
        self.assertIn("missing metadata: Baseline", findings)
        self.assertIn("missing section for question/problem", findings)

    def test_scope_new_reports_only(self):
        self.assertTrue(is_new_report("research/RT-00-EXAMPLE.md"))
        self.assertFalse(is_new_report("research/references/upstream/RT-01.md"))
        self.assertFalse(is_new_report("research/README.md"))

    def test_missing_path_is_reported_not_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run(Path(tmp), ["research/RT-00-DOES-NOT-EXIST.md"])
            self.assertEqual(result["warnings"], 1)
            self.assertEqual(result["reports_checked"], 1)


if __name__ == "__main__":
    unittest.main()
