"""Checks the command inventory and version gates of the native probe runner."""

from pathlib import Path
import unittest

import run_native_probes


class NativeProbeRunnerTests(unittest.TestCase):
    def test_sqlite_suite_contains_all_versioned_native_commands(self):
        commands = run_native_probes.commands_for("sqlite")
        self.assertEqual(
            [name for name, _ in commands],
            [
                "sqlite-cleanup-contracts",
                "sqlite-recovery-matrix",
                "sqlite-snapshot-freshness",
                "sqlite-close-call-boundary",
                "sqlite-close-interleavings",
                "sqlite-close-reentry-and-coverage",
                "sqlite-backup-roles",
                "sqlite-backup-outcomes",
            ],
        )

    def test_all_suite_adds_durable_receipts_and_generated_rust(self):
        commands = run_native_probes.commands_for("all")
        self.assertEqual(len(commands), 10)
        self.assertEqual(commands[-2][0], "sqlite-durable-receipts")
        self.assertEqual(commands[-1][0], "generated-rust-owned-results")

    def test_each_command_points_to_a_tracked_probe_script(self):
        for _name, command in run_native_probes.commands_for("all"):
            script = next(item for item in command if item.endswith(".py"))
            self.assertTrue((run_native_probes.ROOT / script).is_file(), script)

    def test_historical_toolchain_baselines_are_explicit(self):
        self.assertEqual(run_native_probes.EXPECTED_C_SQLITE_VERSION, "3.46.1")
        self.assertIn("c9c2ab54ba1f5f46360f1b4f35d849cd3f080e6fc2b6c60e91b16c63f69aalt1",
                      run_native_probes.EXPECTED_C_SQLITE_SOURCE_ID)
        self.assertEqual(run_native_probes.EXPECTED_RUSTC_VERSION, "1.85.1")
        self.assertEqual(run_native_probes.HISTORICAL_PYTHON_SQLITE_VERSION, "3.53.1")
        self.assertEqual(run_native_probes.EXPECTED_DURABLE_PYTHON_SQLITE_VERSION, "3.53.1")
        self.assertEqual(
            run_native_probes.EXPECTED_DURABLE_PYTHON_SQLITE_SOURCE_ID,
            "2026-05-05 10:34:17 c88b22011a54b4f6fbd149e9f8e4de77658ce58143a1af0e3785e4e6475127e9",
        )


if __name__ == "__main__":
    unittest.main()
