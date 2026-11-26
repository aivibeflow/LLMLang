import contextlib
import io
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog import catalog


class CatalogTests(unittest.TestCase):
    def test_pinned_inventory(self):
        inventory = catalog.load_catalog()
        rows = {row["name"]: row for row in inventory["syscalls"]}
        self.assertEqual(len(rows), 375)
        self.assertEqual(inventory["excluded_x32_records"], 36)
        self.assertEqual(inventory["kernel"]["table_sha256"], catalog.TABLE_HASH)
        self.assertEqual(rows["read"]["number"], 0)
        self.assertEqual(rows["read"]["stage"], 1)
        self.assertTrue(rows["exit"]["noreturn"])
        self.assertEqual(rows["_sysctl"]["kernel_status"], "historical-enosys")
        self.assertEqual(rows["uselib"]["package_status"], "kernel-no-handler")
        self.assertEqual(rows["bpf"]["config"]["requires"], "CONFIG_BPF_SYSCALL")
        self.assertEqual(rows["cachestat"]["config"]["requires"], "CONFIG_CACHESTAT_SYSCALL")
        self.assertEqual(rows["socket"]["config"]["requires"], "CONFIG_NET")
        self.assertIsNone(rows["clock_gettime"]["config"])
        self.assertEqual(rows["clock_gettime"]["behavior_dependencies"][0]["requires"], "CONFIG_POSIX_TIMERS")
        self.assertEqual(sum(row["kernel_status"] == "historical-enosys" for row in rows.values()), 17)
        self.assertTrue(all(row["number"] <= 462 for row in rows.values()))
        self.assertEqual(
            [(interval["first"], interval["last"], interval["status"]) for interval in inventory["reserved_ranges"]],
            [(336, 386, "unallocated"), (387, 423, "reserved-in-table-comment"),
             (463, 511, "unallocated"), (512, 547, "x32-only")],
        )

    def test_diff_ignores_x32_and_detects_native_metadata_changes(self):
        old, _ = catalog.parse_table("0 common read sys_read\n1 64 old\n512 x32 read compat_sys_read\n")
        new, _ = catalog.parse_table(
            "0 64 read sys_read - noreturn\n2 common new sys_new\n513 x32 read compat_sys_read\n"
        )
        changes = catalog.table_diff(old, new)
        self.assertEqual([row["name"] for row in changes["added"]], ["new"])
        self.assertEqual([row["name"] for row in changes["removed"]], ["old"])
        self.assertEqual(len(changes["changed"]), 1)
        self.assertTrue(changes["changed"][0]["after"]["noreturn"])

    def test_parser_rejects_duplicate_and_malformed_rows(self):
        first = "0 common read sys_read\n"
        for second in (
            "0 common write sys_write", "1 arm64 write sys_write", "1 64 read sys_other",
            "1 common write sys_write - never", "invalid table line",
        ):
            with self.subTest(second=second):
                with self.assertRaises(ValueError):
                    catalog.parse_table(first + second)

    def test_detects_source_or_catalog_drift(self):
        with TemporaryDirectory() as directory:
            altered = Path(directory) / "altered"
            altered.write_bytes(catalog.TABLE.read_bytes() + b"# local edit\n")
            with patch.object(catalog, "TABLE", altered):
                with self.assertRaisesRegex(ValueError, "pinned SHA-256"):
                    catalog.load_catalog()
            with patch.object(catalog, "CATALOG", altered):
                with self.assertRaisesRegex(ValueError, "catalog.json differs"):
                    catalog.load_catalog()

    def test_command_variants_stay_with_the_declared_native_family(self):
        profile = {"operation": "io_uring_nop", "scope": "one NOP"}
        variants = [
            {"name": "FIRST", "operation": "io_uring_nop"},
            {"name": "SECOND", "operation": "io_uring_nop"},
        ]
        inventory = catalog.attach_coverage(
            catalog.load_catalog(),
            {"io_uring_enter": [profile], "io_uring_setup": [profile]},
            {("io_uring_enter", "io_uring_nop"): variants},
        )
        rows = {row["name"]: row for row in inventory["syscalls"]}
        self.assertEqual(rows["io_uring_setup"]["commands"]["supported"], [])
        modes = rows["io_uring_enter"]["commands"]["supported"]
        self.assertEqual([item["name"] for item in modes], ["FIRST", "SECOND"])

    def test_complete_requires_admitted_primary_and_each_declared_command(self):
        primary = {"operation": "read", "scope": "bounded adapter profile", "primary": True}
        scoped = {"operation": "io_uring_nop", "scope": "one NOP", "primary": False}
        stale = {"operation": "fcntl_getfl", "primary": True, "diagnostic": "stale"}
        inventory = catalog.attach_coverage(catalog.load_catalog(), {
            "read": [primary],
            "io_uring_enter": [scoped],
            "fcntl": [{"operation": "fcntl_getfd", "primary": True}, stale],
        }, {
            ("fcntl", "fcntl_getfd"): [{"name": "F_GETFD", "operation": "fcntl_getfd"}],
            ("fcntl", "fcntl_getfl"): [{"name": "F_GETFL", "operation": "fcntl_getfl"}],
        })
        rows = {row["name"]: row for row in inventory["syscalls"]}
        self.assertEqual(rows["read"]["package_status"], "ready")
        self.assertEqual(rows["read"]["primary_providers"], ["read"])
        self.assertEqual(rows["io_uring_enter"]["package_status"], "scoped-admission")
        self.assertEqual(rows["fcntl"]["package_status"], "scoped-admission")
        self.assertEqual([entry["name"] for entry in rows["fcntl"]["commands"]["unavailable"]], ["F_GETFL"])

    def test_scoped_admission_and_stale_command_are_distinct_from_complete(self):
        inventory = catalog.attach_coverage(catalog.load_catalog(), {
            "read": [{"operation": "read", "scope": "bounded syscall adapter profile"}],
            "fcntl": [
                {"operation": "fcntl_getfd", "scope": "bounded syscall adapter profile"},
                {"operation": "fcntl_getfl", "diagnostic": "stale"},
            ],
            "write": [{"operation": "write", "diagnostic": "stale"}],
        }, {
            ("fcntl", "fcntl_getfd"): [{"name": "F_GETFD", "operation": "fcntl_getfd"}],
            ("fcntl", "fcntl_getfl"): [{"name": "F_GETFL", "operation": "fcntl_getfl"}],
        })
        rows = {row["name"]: row for row in inventory["syscalls"]}
        self.assertEqual(rows["read"]["package_status"], "scoped-admission")
        self.assertEqual(rows["write"]["package_status"], "unavailable-admission")
        self.assertEqual([entry["name"] for entry in rows["fcntl"]["commands"]["supported"]], ["F_GETFD"])
        self.assertEqual(len(catalog.incomplete_operations(inventory)), 358)
        with patch.object(catalog, "package_coverage", return_value=inventory):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as errors:
                with self.assertRaises(SystemExit) as failure:
                    catalog.main(["check", "--require-complete"])
        self.assertEqual(failure.exception.code, 1)
        self.assertIn("358 active entries lack complete readiness", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
