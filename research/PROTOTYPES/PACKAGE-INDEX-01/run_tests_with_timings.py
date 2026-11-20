"""Run unittest discovery and report per-test wall-clock durations."""
from __future__ import annotations

import json
import time
import unittest


class TimedResult(unittest.TextTestResult):
    def startTest(self, test):
        self._test_started = time.perf_counter()
        super().startTest(test)

    def stopTest(self, test):
        elapsed = time.perf_counter() - self._test_started
        self.test_durations.append((elapsed, test.id()))
        super().stopTest(test)


class TimedRunner(unittest.TextTestRunner):
    resultclass = TimedResult

    def _makeResult(self):
        result = super()._makeResult()
        result.test_durations = []
        return result


def main() -> int:
    suite = unittest.defaultTestLoader.discover(".")
    started = time.perf_counter()
    result = TimedRunner(verbosity=2).run(suite)
    total = time.perf_counter() - started

    print("TEST_TIMING_SUMMARY " + json.dumps({
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "total_seconds": round(total, 6),
        "slowest_tests": [
            {"test": name, "seconds": round(seconds, 6)}
            for seconds, name in sorted(result.test_durations, reverse=True)[:20]
        ],
    }, sort_keys=True), flush=True)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
