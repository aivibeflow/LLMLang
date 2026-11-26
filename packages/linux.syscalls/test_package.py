"""Binding and admission tests for the Linux syscall source profile."""

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

import package


class PackageBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.operations = package.load_contracts()
        cls.files = package.provider_files()
        cls.bindings = package.current_bindings(cls.operations, cls.files)

    def test_public_required_and_provided_contracts_have_distinct_roles(self):
        read = self.bindings["read"]
        self.assertEqual(read["required_contract"], read["public_contract"])
        self.assertNotEqual(read["public_contract"], read["provided_contract"])
        self.assertEqual(read["implementation"]["native_entries"], {"read": 0})

    def test_binding_detects_changed_provider_and_keeps_earlier_pin(self):
        old = self.bindings["read"]
        modified = dict(self.files, **{"src/lib.rs": self.files["src/lib.rs"] + b"\n// replacement\n"})
        new = package.current_bindings(self.operations, modified)["read"]
        self.assertNotEqual(old["impl_hash"], new["impl_hash"])
        self.assertEqual(old["interface_revision"], new["interface_revision"])
        with self.assertRaisesRegex(package.PackageError, "stale"):
            package.resolve(["read"], {"read": old}, {"read": new})
        self.assertEqual(package.resolve(["read"], {"read": old}, self.bindings), {"read": old})
        self.assertNotEqual(package.admission_identity(old, {}), package.admission_identity(new, {}))

    def test_native_abi_drift_is_rejected(self):
        with self.assertRaisesRegex(package.PackageError, "number mismatch for read"):
            package.verify_native_numbers({"read": 0}, {"src/abi.rs": b"const READ: usize = 1;"})

    def test_missing_or_ambiguous_binding_is_rejected(self):
        with self.assertRaisesRegex(package.PackageError, "missing pinned"):
            package.resolve(["read"], {}, self.bindings)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lock.json"
            path.write_text('{"schema":"llmlang.linux.syscalls.lock.v1","bindings":{"read":{},"read":{}}}')
            with self.assertRaisesRegex(package.PackageError, "ambiguous"):
                package.read_lock(path, ["read"])

    def test_admission_rejects_contract_or_evidence_for_another_subject(self):
        read = self.operations["read"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "admissions.json"
            subject = package.admission_identity(self.bindings["write"], package.evidence_inputs())
            path.write_text(json.dumps({
                "schema": "llmlang.linux.syscalls.admissions.v1",
                "operations": {"read": {"subject": subject, "body": "BOUNDED_NATIVE_TEST", "cases": ["fixture"]}},
            }))
            with self.assertRaisesRegex(package.PackageError, "stale exact evidence"):
                package.check_evidence({"read": self.bindings["read"]}, self.operations, path)
            stronger = replace(read.provided, preconditions={**read.provided.preconditions, "test": "stronger"})
            with self.assertRaisesRegex(package.PackageError, "does not refine"):
                package.check_evidence(
                    {"read": self.bindings["read"]}, {"read": replace(read, provided=stronger)}, path,
                )


if __name__ == "__main__":
    unittest.main()
